"""Manage an MCP Server sidecar."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from metisa_common.specification_helper import generate_image_tag
from metisa_common.specification_models import MetisaSpecification

from ..docker.docker_container import (
    create_docker_container,
    inspect_docker_container,
    start_docker_container,
)
from ..docker.docker_image import (
    build_docker_image,
    docker_image_exists,
)
from ..sandbox_context import SandboxContext
from .mcp_server_workspace import (
    MCP_SERVER_MODULE_NAME,
    create_staged_source_directory,
)

_IMAGE_FORMAT_VERSION = 1
_MCP_SERVER_IMAGE_NAME = "metisa-mcp-server"
_MCP_SERVER_NETWORK_ALIAS = "metisa-mcp-server"
_GUEST_SOURCE_DIR = "/sandbox-source"
_GUEST_WORK_DIR = "/sandbox-work"
_GUEST_PYTHON_VENV = "/opt/metisa-venv"


def create_mcp_server_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
) -> str:
    """Create the MCP Server container and connect it to the Docker network."""
    image_name = _ensure_mcp_server_image_exists(specification)
    container_name = _create_mcp_server_container_name(sandbox_context.run_identifier)

    staged_source_path = create_staged_source_directory(sandbox_context)    

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        sandbox_context.private_network_name,
        "--network-alias",
        _MCP_SERVER_NETWORK_ALIAS,
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

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/tmp:rw,size=16m,nosuid,nodev,noexec",
        ]
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

    # Drop all Linux capabilities for the container.
    # https://man7.org/linux/man-pages/man7/capabilities.7.html
    # Docker already excludes more dangerous capabilities such as
    # SYS_ADMIN, NET_ADMIN, SYS_PTRACE, and SYS_MODULE by default.
    arguments.extend(["--cap-drop", "ALL"])

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

    # Mount the necessary volumes.
    arguments.extend(
        [
            "--volume",
            f"{staged_source_path}:{_GUEST_SOURCE_DIR}:ro",
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

    # Set the working directory for the container.
    arguments.extend(
        [
            "--workdir",
            _GUEST_SOURCE_DIR,
        ]
    )    

    # Set environment variables for the container.
    environs.extend(
        [
            "METISA_RUNTIME_ROLE=landlock",
        ]
    )

    for environ in environs:
        arguments.extend(
            [
                "--env",
                environ,
            ]
        )

    # The image name must be specified last in the arguments list.
    arguments.extend(
        [
            image_name,
        ]
    )

    # The command to execute within the container.
    arguments.extend(
        [
            f"{_GUEST_PYTHON_VENV}/bin/python",
            "-I",  # Run the Python interpreter in isolated, no-bytecode mode
            "-B",  # Don't write .pyc files on import
            "-m",
            "uvicorn",
            f"{MCP_SERVER_MODULE_NAME}.server:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
    )

    create_docker_container(arguments)

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("MCP Server sidecar failed to start.")

    return container_name


def _ensure_mcp_server_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_MCP_SERVER_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_mcp_server_image(specification, image_reference)
    return image_reference


def _create_mcp_server_container_name(
    run_identifier: str,
) -> str:
    return f"mcp-server-{run_identifier}"


def _create_mcp_server_image(
    specification: MetisaSpecification,
    image_reference: str,
) -> None:
    dockerfile_location = _get_dockerfile_location()
    build_context_path = dockerfile_location.parent

    temporary_dir = tempfile.mkdtemp()

    requirements_txt = build_context_path / "requirements.txt"
    shutil.copy(requirements_txt, temporary_dir)

    try:
        build_docker_image(
            image_reference=image_reference,
            dockerfile_path=dockerfile_location,
            build_context_path=build_context_path,
            named_build_contexts={"temporary_dir": Path(temporary_dir)},
        )
    finally:
        shutil.rmtree(temporary_dir)


def _get_dockerfile_location() -> Path:
    dockerfile_location = Path(__file__).with_name("dockerfile")
    if not dockerfile_location.exists():
        raise RuntimeError("Dockerfile is not available.")
    return dockerfile_location


def _generate_image_tag(
    specification: MetisaSpecification,
) -> str:
    if specification.mcp_server is None:
        raise RuntimeError("Specification did not contain an [mcp_server] table.")
    collection: list[str] = list(specification.mcp_server.tools)
    collection.extend(list(specification.mcp_server.resources))
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"
