"""Manage a Documents sidecar."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    get_resolved_environs_for_documents,
)
from metisa_common.specification_models import MetisaSpecification

from .._docker._docker_container import (
    create_docker_container,
    inspect_docker_container,
    start_docker_container,
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
_GUEST_DOCS_DIR = "/sandbox-docs"
_DOCUMENTS_ALIAS = "metisa-documents"
_DOCUMENTS_IMAGE_NAME = "metisa-documents"


def create_documents_definition() -> SandboxContainer:
    """Return the definition of the Documents container."""
    return SandboxContainer(
        "Documents",
        "documents",
        log_folder="documents",
        log_files=[],
    )


def create_documents_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create and start a Documents sidecar container."""
    if not specification.documents:
        raise RuntimeError("Metisa specification did not include a document section.")
    image_name = _ensure_documents_image_exists(specification)
    container_name = _create_documents_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the Documents container.")
    network_name = container_creation_context.network_names[0]

    local_docs_dir = specification.documents.local_directory
    if not local_docs_dir:
        raise RuntimeError("Local documents directory is not specified.")
    local_docs_path = Path.cwd() / local_docs_dir
    if not local_docs_path.is_dir():
        raise RuntimeError(f"Documents directory does not exist: {local_docs_path}")

    staged_docs_path = sandbox_context.host_run_path / "documents"
    staged_docs_path.mkdir(parents=True, exist_ok=True)

    for filename in os.listdir(local_docs_dir):
        source_file = local_docs_path / filename
        if source_file.is_file():
            shutil.copy2(source_file, staged_docs_path)

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
        "--network-alias",
        _DOCUMENTS_ALIAS,
    ]

    # Mount the necessary volumes.
    arguments.extend(
        [
            "--volume",
            f"{staged_docs_path}:{_GUEST_DOCS_DIR}:ro",
        ]
    )

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/tmp:rw,size=64m,nosuid,nodev,noexec",
        ]
    )

    specified_environs = get_resolved_environs_for_documents(specification)
    environs.extend(specified_environs)

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="librarian",
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
        raise RuntimeError("Documents sidecar failed to start.")

    return ContainerCreationResult(container_name, staged_source=staged_docs_path)


def _ensure_documents_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_DOCUMENTS_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_documents_image(specification, image_reference)
    return image_reference


def _create_documents_container_name(
    run_identifier: str,
) -> str:
    return f"documents-{run_identifier}"


def _create_documents_image(
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
