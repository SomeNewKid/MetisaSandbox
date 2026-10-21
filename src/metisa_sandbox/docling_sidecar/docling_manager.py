"""Manage a Docling sidecar."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    get_resolved_environs_for_docling,
)
from metisa_common.specification_models import (
    MetisaSpecification,
)

from ..docker.docker_container import (
    create_docker_container,
    inspect_docker_container,
    start_docker_container,
)
from ..docker.docker_hardening import (
    configure_http_proxy,
    harden_docker_container,
)
from ..docker.docker_image import (
    build_docker_image,
    docker_image_exists,
)
from ..sandbox_models import (
    ContainerCreationContext,
    ContainerCreationResult,
    SandboxContainer,
    SandboxContext,
)
from .docling_workspace import (
    DOCLING_MODULE_NAME,
    create_staged_source_directory,
)

_IMAGE_FORMAT_VERSION = 1
_DOCLING_IMAGE_NAME = "metisa-docling"
_DOCLING_NETWORK_ALIAS = "metisa-docling"
_GUEST_SOURCE_DIR = "/sandbox-source"
_GUEST_PYTHON_VENV = "/opt/metisa-venv"
_USE_SQUID_PROXY = False  # Disallow Docling accessing the internet


def create_docling_definition() -> SandboxContainer:
    """Return the definition of the Docling container."""
    return SandboxContainer(
        "Docling",
        "docling",
        log_folder="docling",
        log_files=[],
    )


def create_docling_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create the Docling container and connect it to the Docker network."""
    embedding_model = container_creation_context.settings.get("embedding_model", None)
    if embedding_model is None:
        error = "Embedding model must be specified for the Docling container."
        raise RuntimeError(error)
    if not isinstance(embedding_model, str):
        error = "Embedding model must be a string for the Docling container."
        raise RuntimeError(error)
    if not embedding_model:
        error = "Embedding model cannot be empty for the Docling container."
        raise RuntimeError(error)

    image_name = _ensure_docling_image_exists(specification, embedding_model)
    container_name = _create_docling_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the Docling container.")
    network_name = container_creation_context.network_names[0]

    staged_source_path = create_staged_source_directory(sandbox_context)

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
        "--network-alias",
        _DOCLING_NETWORK_ALIAS,
    ]

    # Mount the necessary volumes.
    arguments.extend(
        [
            "--volume",
            f"{staged_source_path}:{_GUEST_SOURCE_DIR}:ro",
        ]
    )

    # Set the working directory for the container.
    arguments.extend(
        [
            "--workdir",
            _GUEST_SOURCE_DIR,
        ]
    )

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/tmp:rw,size=64m,nosuid,nodev,noexec",
        ]
    )

    # Configure use of Squid Proxy, potentially
    if _USE_SQUID_PROXY:
        squid_proxy_url = container_creation_context.squid_proxy_url
        configure_http_proxy(environs, squid_proxy_url)

    # Get environment variables
    specified_environs = get_resolved_environs_for_docling(specification)
    environs.extend(specified_environs)

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="librarian",
        number_container_processes=128,
        cpu_count=2,
        memory="2g",
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
            "-u",  # makes stdout and stderr unbuffered
            "-m",
            f"{DOCLING_MODULE_NAME}.server",
        ]
    )

    create_docker_container(arguments)

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("Docling sidecar failed to start.")

    return ContainerCreationResult(container_name, staged_source=staged_source_path)


def _ensure_docling_image_exists(
    specification: MetisaSpecification,
    embedding_model: str,
) -> str:
    if not embedding_model:
        error = "Embedding model must be specified for the Docling container."
        raise RuntimeError(error)

    image_tag = _generate_image_tag(specification, embedding_model)
    image_reference = f"{_DOCLING_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_docling_image(specification, image_reference, embedding_model)
    return image_reference


def _create_docling_container_name(
    run_identifier: str,
) -> str:
    return f"docling-{run_identifier}"


def _create_docling_image(
    specification: MetisaSpecification,
    image_reference: str,
    embedding_model: str,
) -> None:
    if not embedding_model:
        error = "Embedding model must be specified for the Docling container."
        raise RuntimeError(error)

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
            build_args=[f"TOKENIZER_MODEL={embedding_model}"],
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
    embedding_model: str,
) -> str:
    collection: list[str] = [embedding_model]
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"
