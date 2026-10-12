"""Manage a Jina Reader sidecar."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    get_resolved_environs_for_jina_reader,
)
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

_IMAGE_FORMAT_VERSION = 1
_JINA_READER_ALIAS = "metisa-jina-reader"
_JINA_READER_IMAGE_NAME = "metisa-jina-reader-proxy"
_USE_SQUID_PROXY = True


def create_jina_reader_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_url: str | None,
) -> str:
    """Create the Jina Reader container and connect it to the Docker network."""
    image_name = _ensure_jina_reader_image_exists(specification)
    container_name = _create_jina_reader_container_name(sandbox_context.run_identifier)

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        sandbox_context.backend_network_name,
        "--network-alias",
        _JINA_READER_ALIAS,
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

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/tmp:rw,size=64m,nosuid,nodev,noexec",
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
            "512",
        ]
    )

    # Set CPU limits for the container.
    arguments.extend(
        [
            "--cpus",
            "2",
        ]
    )

    # Set memory limits for the container.
    arguments.extend(
        [
            "--memory",
            "1g",
            "--memory-swap",  # no additional swap beyond the memory limit
            "1g",
        ]
    )

    # Set the open file descriptor limits for the container.
    # A file descriptor is a small non-negative integer that
    # a Unix process uses as a handle to an open operating-system resource.
    # Limiting descriptors protects against accidental or hostile resource exhaustion.
    arguments.extend(
        [
            "--ulimit",
            "nofile=1024:1024",
        ]
    )

    # Set the per-user process limits for the container.
    arguments.extend(
        [
            "--ulimit",
            "nproc=512:512",
        ]
    )

    # Set the file size limits for the container.
    # Disabled, because it broke Jina Reader, even with larger values.
    # arguments.extend(
    #     [
    #         "--ulimit",
    #         "fsize=1048576:1048576",
    #     ]
    # )

    # Require privileges when binding ports below 1024.
    arguments.extend(
        [
            "--sysctl",
            "net.ipv4.ip_unprivileged_port_start=1024",
        ]
    )

    # Configure use of Squid Proxy
    if squid_proxy_url is not None and _USE_SQUID_PROXY:
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

    specified_environs = get_resolved_environs_for_jina_reader(specification)
    environs.extend(specified_environs)

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
    create_docker_container(arguments)

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("Jina Reader sidecar failed to start.")

    return container_name


def _ensure_jina_reader_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_JINA_READER_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_jina_reader_image(specification, image_reference)
    return image_reference


def _create_jina_reader_container_name(
    run_identifier: str,
) -> str:
    return f"jina-reader-{run_identifier}"


def _create_jina_reader_image(
    specification: MetisaSpecification,
    image_reference: str,
) -> None:
    dockerfile_location = _get_dockerfile_location()
    build_context_path = dockerfile_location.parent

    build_docker_image(
        image_reference=image_reference,
        dockerfile_path=dockerfile_location,
        build_context_path=build_context_path,
    )


def _get_dockerfile_location() -> Path:
    dockerfile_location = Path(__file__).with_name("dockerfile")
    if not dockerfile_location.exists():
        raise RuntimeError("Dockerfile is not available.")
    return dockerfile_location


def _generate_image_tag(
    specification: MetisaSpecification,
) -> str:
    collection: list[str] = []
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"
