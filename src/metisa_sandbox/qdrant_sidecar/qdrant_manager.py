"""Manage a Qdrant sidecar."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    resolve_environs,
)
from metisa_common.specification_models import MetisaSpecification

from .._docker._docker_container import (
    create_docker_container,
)
from .._docker._docker_hardening import (
    harden_docker_container,
)
from .._docker._docker_image import (
    build_docker_image,
    docker_image_exists,
)
from .._sandbox_models import (
    ContainerCreationContext,
    ContainerCreationResult,
    SandboxContainer,
    SandboxContext,
)

_IMAGE_FORMAT_VERSION = 1
_QDRANT_ALIAS = "metisa-qdrant"
_QDRANT_IMAGE_NAME = "metisa-qdrant"


def create_qdrant_definition() -> SandboxContainer:
    """Return the definition of the Qdrant container."""
    return SandboxContainer(
        "Qdrant",
        "qdrant",
        log_folder="qdrant",
        log_files=[],
    )


def create_qdrant_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create and start a Qdrant sidecar container."""
    if not specification.qdrant:
        raise RuntimeError("Metisa specification did not include a document section.")
    image_name = _ensure_qdrant_image_exists(specification)
    container_name = _create_qdrant_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the Qdrant container.")
    network_name = container_creation_context.network_names[0]

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
        "--network-alias",
        _QDRANT_ALIAS,
    ]

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/qdrant/storage:rw,size=128m,uid=1000,gid=1000,mode=0700,nosuid,nodev,noexec",
            "--tmpfs",
            "/qdrant/snapshots:rw,size=128m,uid=1000,gid=1000,mode=0700,nosuid,nodev,noexec",
            "--tmpfs",
            "/tmp:rw,size=64m,nosuid,nodev,noexec",
        ]
    )

    # Get environment variables
    resolved_environs = resolve_environs(specification.qdrant.environs)
    environs.extend(resolved_environs)

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="qdrant",
        memory="512m",
        number_container_processes=128,
        number_of_files=1024,
        file_size_limit=None,
    )

    # The image name must be specified last in the arguments list.
    arguments.extend(
        [
            image_name,
        ]
    )

    create_docker_container(arguments)

    return ContainerCreationResult(container_name)


def _ensure_qdrant_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_QDRANT_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_qdrant_image(specification, image_reference)
    return image_reference


def _create_qdrant_container_name(
    run_identifier: str,
) -> str:
    return f"qdrant-{run_identifier}"


def _create_qdrant_image(
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
