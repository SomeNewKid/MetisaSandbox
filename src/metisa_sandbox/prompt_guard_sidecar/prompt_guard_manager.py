"""Manage a Prompt Guard sidecar."""

from __future__ import annotations

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
from ._prompt_guard_workspace import (
    PROMPT_GUARD_MODULE_NAME,
    create_staged_source_directory,
)

_IMAGE_FORMAT_VERSION = 1
_PROMPT_GUARD_IMAGE_NAME = "metisa-prompt-guard"
_PROMPT_GUARD_NETWORK_ALIAS = "metisa-prompt-guard"
_GUEST_SOURCE_DIR = "/sandbox-source"
_GUEST_PYTHON_VENV = "/opt/metisa-venv"


def create_prompt_guard_definition() -> SandboxContainer:
    """Return the definition of the Prompt Guard container."""
    return SandboxContainer(
        "Prompt Guard",
        "prompt_guard",
        log_folder="prompt-guard",
        log_files=[],
    )


def create_prompt_guard_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create the Prompt Guard container and connect it to the Docker network."""
    image_name = _ensure_prompt_guard_image_exists(specification)
    container_name = _create_prompt_guard_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the Prompt Guard container.")
    network_name = container_creation_context.network_names[0]

    staged_source_path = create_staged_source_directory(sandbox_context)

    local_models_directory = specification.settings.get("local_models_directory")
    local_models_dir_path = (
        Path(local_models_directory) if local_models_directory else Path.cwd()
    )

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
        "--network-alias",
        _PROMPT_GUARD_NETWORK_ALIAS,
    ]

    # Mount the necessary volumes.
    arguments.extend(
        [
            "--volume",
            f"{staged_source_path}:{_GUEST_SOURCE_DIR}:ro",
        ]
    )

    # Mount the Meta LLaMA model.
    local_llama_path = (
        local_models_dir_path
        / "meta-llama"
        / "Llama-Prompt-Guard-2-22M"
        / "11614a155199674a0a95e6602d6ab0417b790ed0"
    )
    if not local_llama_path.is_dir():
        raise FileNotFoundError(f"Model files not found at {local_llama_path}")
    local_llama_location = str(local_llama_path)
    container_llama_location = "/models/llama-prompt-guard"
    arguments.extend(
        [
            "--mount",
            (
                "type=bind,"
                f"source={local_llama_location},"
                f"target={container_llama_location},"
                "readonly"
            ),
        ]
    )

    # Mount the Koala model.
    local_koala_path = (
        local_models_dir_path
        / "KoalaAI"
        / "Text-Moderation"
        / "838ade0edb66dcffc5532d08ff6ed5c899abfb5c"
    )
    if not local_koala_path.is_dir():
        raise FileNotFoundError(f"Model files not found at {local_koala_path}")
    local_koala_location = str(local_koala_path)
    container_koala_location = "/models/koala-text-moderation"
    arguments.extend(
        [
            "--mount",
            (
                "type=bind,"
                f"source={local_koala_location},"
                f"target={container_koala_location},"
                "readonly"
            ),
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
        username="guardian",
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
            f"{PROMPT_GUARD_MODULE_NAME}.server",
        ]
    )

    create_docker_container(arguments)

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("Prompt Guard sidecar failed to start.")

    return ContainerCreationResult(container_name, staged_source=staged_source_path)


def _ensure_prompt_guard_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_PROMPT_GUARD_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_prompt_guard_image(specification, image_reference)
    return image_reference


def _create_prompt_guard_container_name(
    run_identifier: str,
) -> str:
    return f"prompt-guard-{run_identifier}"


def _create_prompt_guard_image(
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
    collection: list[str] = []
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"
