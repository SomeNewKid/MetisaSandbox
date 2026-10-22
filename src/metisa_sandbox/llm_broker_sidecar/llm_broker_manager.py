"""Manage an LLM Broker sidecar."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    get_resolved_environs_for_llm_broker,
)
from metisa_common.specification_models import (
    LlmBrokerSpecification,
    MetisaSpecification,
)

from .._docker._docker_container import (
    create_docker_container,
    inspect_docker_container,
    start_docker_container,
)
from .._docker._docker_hardening import (
    configure_http_proxy,
    harden_docker_container,
)
from .._docker._docker_image import (
    build_docker_image,
    docker_image_exists,
)
from .._docker._docker_network import (
    connect_container_to_docker_network,
)
from .._sandbox_models import (
    ContainerCreationContext,
    ContainerCreationResult,
    SandboxContainer,
    SandboxContext,
)
from ._llm_broker_workspace import (
    LLM_BROKER_MODULE_NAME,
    create_staged_source_directory,
)

_IMAGE_FORMAT_VERSION = 1
_LLM_BROKER_IMAGE_NAME = "metisa-llm-broker"
_LLM_BROKER_NETWORK_ALIAS = "metisa-llm-broker"
_LLM_BROKER_PORT = 8000
_GUEST_SOURCE_DIR = "/sandbox-source"
_GUEST_PYTHON_VENV = "/opt/metisa-venv"
_USE_SQUID_PROXY = True


def create_llm_broker_definition() -> SandboxContainer:
    """Return the definition of the LLM Broker container."""
    return SandboxContainer(
        "LLM Broker",
        "llm_broker",
        log_folder="llm-broker",
        log_files=["/sandbox-source/metisa.json"],
    )


def create_llm_broker_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create the LLM Broker container and connect it to the Docker network."""
    if specification.llm_broker is None:
        raise RuntimeError("Metisa specification has no [llm_broker] section.")

    image_name = _ensure_llm_broker_image_exists(specification)
    container_name = _create_llm_broker_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the LLM Broker container.")
    network_name = container_creation_context.network_names[0]

    staged_source_path = create_staged_source_directory(sandbox_context)

    metisa_json_file = staged_source_path / "metisa.json"
    metisa_json = _create_metisa_json(specification.llm_broker)
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
        _LLM_BROKER_NETWORK_ALIAS,
    ]

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/tmp:rw,size=16m,nosuid,nodev,noexec",
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

    # Configure use of Squid Proxy
    squid_proxy_url = container_creation_context.squid_proxy_url
    if squid_proxy_url is not None and _USE_SQUID_PROXY:
        configure_http_proxy(environs, squid_proxy_url)

    specified_environs = get_resolved_environs_for_llm_broker(specification)
    environs.extend(specified_environs)

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="broker",
        number_of_files=256,
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
            "uvicorn",
            f"{LLM_BROKER_MODULE_NAME}.server:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(_LLM_BROKER_PORT),
        ]
    )

    create_docker_container(arguments)

    if len(container_creation_context.network_names) > 1:
        for network_name in container_creation_context.network_names[1:]:
            connect_container_to_docker_network(
                container_name=container_name,
                network_name=network_name,
                aliases=(_LLM_BROKER_NETWORK_ALIAS,),
            )

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("LLM Broker sidecar failed to start.")

    return ContainerCreationResult(container_name, staged_source=staged_source_path)


def _ensure_llm_broker_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_LLM_BROKER_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_llm_broker_image(specification, image_reference)
    return image_reference


def _create_llm_broker_container_name(
    run_identifier: str,
) -> str:
    return f"llm-broker-{run_identifier}"


def _create_llm_broker_image(
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
    if specification.llm_broker is None:
        raise RuntimeError("Specification did not contain an [llm_broker] table.")
    collection = []
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"


def _create_metisa_json(
    llm_broker: LlmBrokerSpecification | None,
) -> str:
    local_models: list[str] = []
    if llm_broker is not None:
        for alias in llm_broker.local_models:
            local_models.append(alias)

    online_models: list[str] = []
    if llm_broker is not None:
        for alias in llm_broker.online_models:
            online_models.append(alias)

    config = {
        "local_models": local_models,
        "online_models": online_models,
    }

    return json.dumps(config, indent=2)
