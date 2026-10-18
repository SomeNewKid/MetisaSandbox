"""Provides utility methods for managing the Docker workload container."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import get_resolved_environs_for_metisa
from metisa_common.specification_models import MetisaSpecification
from metisa_sandbox.docker.docker_container import create_docker_container

from ..sandbox_models import (
    ContainerCreationContext,
    ContainerCreationResult,
    SandboxContainer,
    SandboxContext,
)
from .metisa_container_workspace import (
    LANDLOCK_MODULE_NAME,
    create_staged_source_directory,
)

_GUEST_SOURCE_DIR = "/sandbox-source"
_GUEST_OUTPUT_DIR = "/sandbox-output"
_GUEST_WORK_DIR = "/sandbox-work"
_GUEST_PYTHON_VENV = "/opt/metisa-venv"


def create_metisa_workload_definition() -> SandboxContainer:
    """Return the definition of the Metisa workload container."""
    return SandboxContainer(
        "Metisa Workload",
        "metisa_workload",
        log_folder="metisa",
        log_files=[],
    )


def create_metisa_workload_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create the Metisa Workload container and connect it to the Docker network."""
    creation_settings = container_creation_context.settings

    image_reference = creation_settings.get("image_reference", "")
    if not image_reference:
        raise RuntimeError("Metisa Workload requires an image reference.")
    if not isinstance(image_reference, str):
        raise RuntimeError("Metisa Workload image reference must be a string.")

    workload_module = creation_settings.get("workload_module", "")
    if not workload_module:
        raise RuntimeError("Metisa Workload requires a workload_module.")
    if not isinstance(workload_module, str):
        raise RuntimeError("Metisa Workload workload module must be a string.")

    is_network_required = creation_settings.get("is_network_required", None)
    if not is_network_required:
        raise RuntimeError("Metisa Workload requires a network-required flag.")
    if not isinstance(is_network_required, bool):
        raise RuntimeError("Metisa Workload network-required flag must be a bool.")

    use_squid_proxy = creation_settings.get("use_squid_proxy", None)
    if use_squid_proxy is not None and not isinstance(use_squid_proxy, bool):
        raise RuntimeError("Metisa Workload squid-proxy flag must be a bool.")
    if use_squid_proxy is None:
        use_squid_proxy = False

    staged_source_path = create_staged_source_directory(
        sandbox_context, workload_module
    )

    environs: list[str] = []

    # Initialize the list of Docker run arguments.
    arguments = [
        "--name",
        sandbox_context.workload_container_name,
    ]

    # Configure the network settings for the container
    # based on whether a network is required.
    if is_network_required:
        arguments.extend(
            [
                "--network",
                sandbox_context.workload_network_name,
                "--network-alias",
                "metisa-workload",
            ]
        )
        squid_proxy_url = (
            container_creation_context.squid_proxy_url if is_network_required else None
        )
        if use_squid_proxy and squid_proxy_url is not None:
            no_proxy_destinations = ",".join(
                [
                    "localhost",
                    "127.0.0.1",
                    "::1",
                    "metisa-workload",
                    "metisa-squid",
                    "metisa-mcp-server",
                ]
            )
            environs.extend(
                [
                    f"HTTP_PROXY={squid_proxy_url}",
                    f"HTTPS_PROXY={squid_proxy_url}",
                    f"NO_PROXY={no_proxy_destinations}",
                    f"http_proxy={squid_proxy_url}",
                    f"https_proxy={squid_proxy_url}",
                    f"no_proxy={no_proxy_destinations}",
                ]
            )
    else:
        arguments.extend(
            [
                "--network",
                "none",
            ]
        )

    # Mount the container's root filesystem as strictly read-only
    # Couple with in memory temporary writes (--tmpfs)
    # or with read-write mounted volumes (-volume /host/path:/volume:rw).
    arguments.extend(
        [
            "--read-only",
        ]
    )

    # Linux control groups, or cgroups, organize processes and
    # enforce resource accounting and limits such as:
    # - Memory usage
    # - CPU allocation
    # - Process counts
    # - I/O limits
    # Docker already places each container into one or more cgroups.
    # A cgroup namespace controls how much of that cgroup hierarchy a process can see.
    arguments.extend(
        [
            "--cgroupns",
            "private",
        ]
    )

    # Run as the sandbox user
    uid = 10001  # sandbox user
    gid = 10001  # sandbox group
    arguments.extend(
        ["--user", f"{uid}:{gid}"],
    )

    # Executing another program cannot grant the process privileges
    # it did not already have.  It prevents privilege escalation through:
    # Set-user-ID,
    # Set-group-ID,
    # Executables with Linux file capabilities.
    arguments.extend(
        [
            "--security-opt",
            "no-new-privileges=true",
        ]
    )

    # Specify a seccomp (secure computing mode) profile for the container.
    # The seccomp profile defines a set of system calls that the container
    # is allowed to make (that is, it is a whitelist).
    # This custom seccomp profile started as a copy of the default Docker
    # seccomp profile from commit 6fe7deb1b9fb7c0397a4593480d7d22b9ee8caef.
    seccomp_path = Path(__file__).resolve().with_name("seccomp.json")
    if not seccomp_path.is_file():
        raise ValueError(f"Seccomp profile not found at {seccomp_path}")
    arguments.extend(["--security-opt", f"seccomp={seccomp_path}"])

    # Allocate a pseudo-terminal.
    # Allows Python `input` to get user input from the terminal.
    arguments.extend(
        [
            "--interactive",  # keeps stdin open
            "--tty",  # allocates a pseudo-terminal
        ]
    )

    # Drop all Linux capabilities for the container.
    # https://man7.org/linux/man-pages/man7/capabilities.7.html
    # Docker already excludes more dangerous capabilities such as
    # SYS_ADMIN, NET_ADMIN, SYS_PTRACE, and SYS_MODULE by default.
    arguments.extend(["--cap-drop", "ALL"])

    # Mount the necessary volumes.
    arguments.extend(
        [
            "--volume",
            f"{staged_source_path}:{_GUEST_SOURCE_DIR}:ro",
            "--volume",
            f"{sandbox_context.host_output_path}:{_GUEST_OUTPUT_DIR}:rw",
        ]
    )

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            f"{_GUEST_WORK_DIR}:rw,size=1m,nosuid,nodev,noexec",
            "--tmpfs",
            "/tmp:rw,size=16m,nosuid,nodev,noexec",
        ]
    )

    # Set environment variables for the container.
    environs.extend(
        [
            f"SANDBOX_OUTPUT_DIR={_GUEST_OUTPUT_DIR}",
            "METISA_RUNTIME_ROLE=landlock",
        ]
    )

    # Set the working directory for the container.
    arguments.extend(
        [
            "--workdir",
            _GUEST_SOURCE_DIR,
        ]
    )

    # Without --init, the command supplied after the image
    # becomes PID 1 inside the container.
    # PID 1 has special responsibilities on Linux.
    # In particular, it inherits orphaned descendant processes and
    # must collect, or “reap,” processes that have exited.
    # Ordinary applications are not always designed to perform that role correctly.
    # With --init, Docker inserts its small docker-init process as PID 1.
    arguments.extend(
        [
            "--init",  # correctly reaps exited and orphaned processes.
            "--pids-limit",  # Bounds how many processes the container may have at once
            "64",
        ]
    )

    # Set CPU limits for the container.
    arguments.extend(
        [
            "--cpus",
            "1",
        ]
    )

    # Set memory limits for the container.
    arguments.extend(
        [
            "--memory",
            "128m",
            "--memory-swap",  # no additional swap beyond the memory limit
            "128m",
        ]
    )

    # Set the open file descriptor limits for the container.
    # A file descriptor is a small non-negative integer that
    # a Unix process uses as a handle to an open operating-system resource.
    # Limiting descriptors protects against accidental or hostile resource exhaustion.
    arguments.extend(
        [
            "--ulimit",
            "nofile=256:256",
        ]
    )

    # Set the per-user process limits for the container.
    arguments.extend(
        [
            "--ulimit",
            "nproc=64:64",
        ]
    )

    # Set the file size limits for the container.
    # (Applies to file writes, not to existing files.)
    arguments.extend(
        [
            "--ulimit",
            "fsize=1048576:1048576",
        ]
    )

    # Require privileges when binding ports below 1024.
    arguments.extend(
        [
            "--sysctl",
            "net.ipv4.ip_unprivileged_port_start=1024",
        ]
    )

    specified_environs = get_resolved_environs_for_metisa(specification)
    environs.extend(specified_environs)

    for environ in environs:
        arguments.extend(
            [
                "--env",
                environ,
            ]
        )

    # ---------------- The following switches must be last ----------------

    # The image from which to construct the container.
    arguments.extend(
        [
            image_reference,
        ]
    )

    # The command to execute within the container.
    arguments.extend(
        [
            f"{_GUEST_PYTHON_VENV}/bin/python",
            "-I",  # Run the Python interpreter in isolated, no-bytecode mode
            "-B",  # Don't write .pyc files on import
            "-m",
            LANDLOCK_MODULE_NAME,
            workload_module,
        ]
    )

    create_docker_container(arguments)

    return ContainerCreationResult(
        sandbox_context.workload_container_name,
        staged_source=staged_source_path,
    )
