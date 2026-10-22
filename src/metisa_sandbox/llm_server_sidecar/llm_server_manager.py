"""Manage a LLM Server sidecar."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
)
from metisa_common.specification_models import LlmModel, MetisaSpecification

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

LLM_CONTAINER_ALIAS_PREFIX = "metisa-llm-"
LLM_CONTAINER_NAME_PREFIX = "llm-server-"
_IMAGE_FORMAT_VERSION = 1
_LLM_SERVER_IMAGE_NAME = "metisa-llm-server"


def create_llm_server_definition(
    llm_model_alias: str,
) -> SandboxContainer:
    """Return the definition of the LLM Server container for the given model alias."""
    return SandboxContainer(
        f"LLM Server ({llm_model_alias})",
        f"llm_server_{llm_model_alias.replace('-', '_')}",
        log_folder=f"llm-{llm_model_alias}",
        log_files=[],
    )


def create_llm_server_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create and start LLM Server containers."""
    image_name = _ensure_llm_server_image_exists(specification)

    local_models_directory = specification.settings.get("local_models_directory", "")
    local_models_dir_path = (
        Path(local_models_directory) if local_models_directory else Path.cwd()
    )

    llm_model = container_creation_context.settings.get("llm_model")
    if not llm_model:
        error = "LLM model must be specified in the container creation context."
        raise ValueError(error)
    if not isinstance(llm_model, LlmModel):
        raise TypeError("LLM model must be an instance of LlmModel.")

    container_name = _create_llm_server_container(
        local_models_dir_path, llm_model, sandbox_context, image_name
    )

    return ContainerCreationResult(container_name=container_name)


def _create_llm_server_container(
    local_models_path: Path,
    llm_model: LlmModel,
    sandbox_context: SandboxContext,
    image_name: str,
) -> str:
    container_name = _create_llm_server_container_name(
        llm_model, sandbox_context.run_identifier
    )
    container_alias = _create_llm_server_container_alias(
        llm_model,
    )

    arguments = [
        "--name",
        container_name,
        "--network",
        sandbox_context.backend_network_name,
        "--network-alias",
        container_alias,
    ]

    # Mount the model file into the container.
    local_relative = llm_model.repo.replace("/", "\\")
    local_model_path = (
        local_models_path / local_relative / llm_model.revision / llm_model.filename
    )
    if not local_model_path.is_file():
        raise FileNotFoundError(f"Model file not found at {local_model_path}")
    local_model_location = str(local_model_path)
    container_model_location = f"/models/{llm_model.filename}"
    arguments.extend(
        [
            "--mount",
            (
                "type=bind,"
                f"source={local_model_location},"
                f"target={container_model_location},"
                "readonly"
            ),
        ]
    )

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=[],
        username="llama",
        cpu_count=None,
        memory="3g",
        number_of_files=512,
        health_start_seconds=540,
    )

    # The image name must be specified last in the arguments list.
    arguments.extend(
        [
            image_name,
            "--model",
            container_model_location,
            "--alias",
            llm_model.alias,
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
            "--ctx-size",
            "2048",
            "--parallel",
            "1",
            "--threads",
            "4",
            "--threads-batch",
            "4",
            # "--log-verbosity",
            # "5",
        ]
    )

    create_docker_container(arguments)

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError(f"LLM server '{container_alias}' failed to start.")

    return container_name


def _ensure_llm_server_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_LLM_SERVER_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_llm_server_image(specification, image_reference)
    return image_reference


def _create_llm_server_container_name(
    llm_model: LlmModel,
    run_identifier: str,
) -> str:
    return f"{LLM_CONTAINER_NAME_PREFIX}{run_identifier}-{llm_model.alias}"


def _create_llm_server_container_alias(
    llm_model: LlmModel,
) -> str:
    return f"{LLM_CONTAINER_ALIAS_PREFIX}{llm_model.alias}"


def _create_llm_server_image(
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
