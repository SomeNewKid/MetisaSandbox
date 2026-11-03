"""Manage an Agent Memory sidecar."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from metisa_common.secrets_helper import SECRETS_DIRECTORY
from metisa_common.specification_helper import (
    generate_image_tag,
    resolve_environs,
    resolve_secrets,
)
from metisa_common.specification_models import (
    LlmBrokerSpecification,
    MetisaSpecification,
)

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
from .._docker._docker_network import (
    connect_container_to_docker_network,
)
from .._sandbox_models import (
    ContainerCreationContext,
    ContainerCreationResult,
    SandboxContainer,
    SandboxContext,
)
from .._utilities._secrets_helper import (
    create_secrets_file,
)
from ._agent_memory_workspace import (
    AGENT_MEMORY_MODULE_NAME,
    create_staged_source_directory,
)

_IMAGE_FORMAT_VERSION = 1
_AGENT_MEMORY_IMAGE_NAME = "metisa-agent-memory"
_AGENT_MEMORY_NETWORK_ALIAS = "metisa-agent-memory"
_GUEST_SOURCE_DIR = "/sandbox-source"
_GUEST_PYTHON_VENV = "/opt/metisa-venv"


def create_agent_memory_definition() -> SandboxContainer:
    """Return the definition of the Agent Memory container."""
    return SandboxContainer(
        "Agent Memory",
        "agent_memory",
        log_folder="agent-memory",
        log_files=[],
    )


def create_agent_memory_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
    public_key_pem: bytes,
) -> ContainerCreationResult:
    """Create the Agent Memory container and connect it to the Docker network."""
    if specification.agent_memory is None:
        raise RuntimeError("Metisa specification has no [agent_memory] section.")

    image_name = _ensure_agent_memory_image_exists(specification)
    container_name = _create_agent_memory_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the Agent Memory container.")
    network_name = container_creation_context.network_names[0]

    staged_source_path = create_staged_source_directory(sandbox_context)

    public_key_path = staged_source_path / "metisa-public-key.pem"
    public_key_path.write_bytes(public_key_pem)

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
        "--network-alias",
        _AGENT_MEMORY_NETWORK_ALIAS,
    ]

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
            "--tmpfs",
            (
                f"{SECRETS_DIRECTORY.as_posix()}:"
                "rw,size=64k,nosuid,nodev,noexec,"
                "uid=10012,gid=10012,mode=0700"
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

    # Handle the secrets for the container
    secrets = resolve_secrets(specification.agent_memory.secrets)
    secrets_file, secrets_key = create_secrets_file(staged_source_path, secrets)

    # Get environment variables
    if specification.agent_memory is not None:
        resolved_environs = resolve_environs(specification.agent_memory.environs)
        environs.extend(resolved_environs)

    environs.append(f"METISA_RUN_ID={sandbox_context.run_identifier}")

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="elephant",
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
            f"{AGENT_MEMORY_MODULE_NAME}.server",
        ]
    )

    create_docker_container(arguments)

    if len(container_creation_context.network_names) > 1:
        for network_name in container_creation_context.network_names[1:]:
            connect_container_to_docker_network(
                container_name=container_name,
                network_name=network_name,
                aliases=(_AGENT_MEMORY_NETWORK_ALIAS,),
            )

    return ContainerCreationResult(
        container_name,
        staged_source=staged_source_path,
        secrets_file=secrets_file,
        secrets_key=secrets_key,
    )


def _ensure_agent_memory_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_AGENT_MEMORY_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_agent_memory_image(specification, image_reference)
    return image_reference


def _create_agent_memory_container_name(
    run_identifier: str,
) -> str:
    return f"agent-memory-{run_identifier}"


def _create_agent_memory_image(
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
    if specification.agent_memory is None:
        raise RuntimeError("Specification did not contain an [agent_memory] table.")
    collection = []
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"


def _create_metisa_json(
    agent_memory: LlmBrokerSpecification | None,
) -> str:
    local_models: list[str] = []
    if agent_memory is not None:
        for alias in agent_memory.local_models:
            local_models.append(alias)

    online_models: list[str] = []
    if agent_memory is not None:
        for alias in agent_memory.online_models:
            online_models.append(alias)

    config = {
        "local_models": local_models,
        "online_models": online_models,
    }

    return json.dumps(config, indent=2)
