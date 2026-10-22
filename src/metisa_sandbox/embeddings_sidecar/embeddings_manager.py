"""Manage a Embeddings sidecar."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
)
from metisa_common.specification_models import (
    MetisaSpecification,
)

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
from ._embeddings_workspace import (
    EMBEDDINGS_MODULE_NAME,
    create_staged_source_directory,
)

_IMAGE_FORMAT_VERSION = 1
_EMBEDDINGS_IMAGE_NAME = "metisa-embeddings"
_EMBEDDINGS_NETWORK_ALIAS = "metisa-embeddings"
_GUEST_SOURCE_DIR = "/sandbox-source"
_GUEST_PYTHON_VENV = "/opt/metisa-venv"


def create_embeddings_definition() -> SandboxContainer:
    """Return the definition of the Embeddings container."""
    return SandboxContainer(
        "Embeddings",
        "embeddings",
        log_folder="embeddings",
        log_files=["/sandbox-source/metisa.json"],
    )


def create_embeddings_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create the Embeddings container and connect it to the Docker network."""
    embedding_model = container_creation_context.settings.get("embedding_model", None)
    if embedding_model is None:
        error = "Embedding model must be specified for the Embeddings container."
        raise RuntimeError(error)
    if not isinstance(embedding_model, str):
        error = "Embedding model must be a string for the Embeddings container."
        raise RuntimeError(error)
    if not embedding_model:
        error = "Embedding model cannot be empty for the Embeddings container."
        raise RuntimeError(error)

    image_name = _ensure_embeddings_image_exists(specification, embedding_model)
    container_name = _create_embeddings_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the Embeddings container.")
    network_name = container_creation_context.network_names[0]

    staged_source_path = create_staged_source_directory(sandbox_context)

    metisa_json_file = staged_source_path / "metisa.json"
    metisa_json = _create_metisa_json(embedding_model)
    with metisa_json_file.open("w", encoding="utf-8") as file:
        file.write(metisa_json)

    if not metisa_json_file.exists():
        raise RuntimeError("Could not create metisa.json file.")

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
        "--network-alias",
        _EMBEDDINGS_NETWORK_ALIAS,
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

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="searcher",
        cpu_count=2,
        memory="3g",
        number_of_files=512,
        health_start_seconds=360,
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
            f"{EMBEDDINGS_MODULE_NAME}.server",
        ]
    )

    create_docker_container(arguments)

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("Embeddings sidecar failed to start.")

    return ContainerCreationResult(container_name, staged_source=staged_source_path)


def _ensure_embeddings_image_exists(
    specification: MetisaSpecification,
    embedding_model: str,
) -> str:
    if not embedding_model:
        error = "Embedding model must be specified for the Embeddings container."
        raise RuntimeError(error)

    image_tag = _generate_image_tag(specification, embedding_model)
    image_reference = f"{_EMBEDDINGS_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_embeddings_image(specification, image_reference, embedding_model)
    return image_reference


def _create_embeddings_container_name(
    run_identifier: str,
) -> str:
    return f"embeddings-{run_identifier}"


def _create_embeddings_image(
    specification: MetisaSpecification,
    image_reference: str,
    embedding_model: str,
) -> None:
    if not embedding_model:
        error = "Embedding model must be specified for the Embeddings container."
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


def _create_metisa_json(
    embedding_model: str,
) -> str:
    config = {
        "embedding_model": embedding_model,
    }
    return json.dumps(config, indent=2)
