"""Manage a Code Execution sidecar."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    get_resolved_environs_for_code_execution,
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
_CODE_EXECUTION_ALIAS = "metisa-code-execution"
_CODE_EXECUTION_IMAGE_NAME = "metisa-code-execution"


def create_code_execution_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
) -> str:
    """Create and start a Code Execution sidecar container."""
    image_name = _ensure_code_execution_image_exists(specification)
    container_name = _create_code_execution_container_name(
        sandbox_context.run_identifier
    )

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        sandbox_context.backend_network_name,
        "--network-alias",
        _CODE_EXECUTION_ALIAS,
    ]

    # Mount the container's root filesystem as strictly read-only
    # Couple with in memory temporary writes (--tmpfs)
    # or with read-write mounted volumes (-volume /host/path:/volume:rw).
    arguments.extend(
        [
            "--read-only",
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

    specified_environs = get_resolved_environs_for_code_execution(specification)
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
        raise RuntimeError("Code Execution sidecar failed to start.")

    return container_name


def _ensure_code_execution_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_CODE_EXECUTION_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_code_execution_image(specification, image_reference)
    return image_reference


def _create_code_execution_container_name(
    run_identifier: str,
) -> str:
    return f"code-execution-{run_identifier}"


def _create_code_execution_image(
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
