"""Provides utility methods for managing the Docker workload container."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import get_resolved_environs_for_metisa
from metisa_common.specification_models import Capability, MetisaSpecification

from ..sandbox_context import SandboxContext
from .metisa_container_workspace import LANDLOCK_MODULE_NAME

_GUEST_SOURCE_DIR = "/sandbox-source"
_GUEST_OUTPUT_DIR = "/sandbox-output"
_GUEST_WORK_DIR = "/sandbox-work"
_GUEST_PYTHON_VENV = "/opt/metisa-venv"


def create_docker_run_arguments(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    image_reference: str,
    staged_source_path: Path,
    workload_module: str,
    is_network_required: bool,
    squid_proxy_url: str | None,
) -> list[str]:
    """Create the list of Docker run arguments for the workload container."""
    is_interactive = Capability.INTERACTIVE in specification.capabilities

    environs: list[str] = []

    # Initialize the list of Docker run arguments.
    arguments = [
        "--name",
        sandbox_context.workload_container_name,
    ]

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

    # Configure the network settings for the container
    # based on whether a network is required.
    if is_network_required:
        arguments.extend(
            [
                "--network",
                sandbox_context.private_network_name,
                "--network-alias",
                "metisa-workload",
            ]
        )
        if squid_proxy_url is not None:
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

    # Allocate a pseudo-terminal if the sandbox is interactive.
    # Allows Python `input` to get user input from the terminal.
    if is_interactive:
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

    return arguments
