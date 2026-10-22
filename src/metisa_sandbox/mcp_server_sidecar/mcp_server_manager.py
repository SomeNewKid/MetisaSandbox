"""Manage an MCP Server sidecar."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    get_resolved_environs_for_mcp_server,
)
from metisa_common.specification_models import (
    McpServerSpecification,
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
from ._mcp_server_workspace import (
    MCP_SERVER_MODULE_NAME,
    create_staged_source_directory,
)

_IMAGE_FORMAT_VERSION = 1
_MCP_SERVER_IMAGE_NAME = "metisa-mcp-server"
_MCP_SERVER_NETWORK_ALIAS = "metisa-mcp-server"
_MCP_SERVER_PORT = 8000
_GUEST_SOURCE_DIR = "/sandbox-source"
_GUEST_PYTHON_VENV = "/opt/metisa-venv"
_USE_SQUID_PROXY = True


def create_mcp_server_definition() -> SandboxContainer:
    """Return the definition of the MCP Server container."""
    return SandboxContainer(
        "MCP Server",
        "mcp_server",
        log_folder="mcp-server",
        log_files=["/sandbox-source/metisa.json"],
    )


def create_mcp_server_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create the MCP Server container and connect it to the Docker network."""
    if specification.mcp_server is None:
        raise RuntimeError("Metisa specification has no [mcp_server] section.")

    image_name = _ensure_mcp_server_image_exists(specification)
    container_name = _create_mcp_server_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the HAProxy container.")
    network_name = container_creation_context.network_names[0]

    staged_source_path = create_staged_source_directory(sandbox_context)

    metisa_json_file = staged_source_path / "metisa.json"
    metisa_json = _create_metisa_json(specification.mcp_server)
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
        _MCP_SERVER_NETWORK_ALIAS,
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

    specified_environs = get_resolved_environs_for_mcp_server(specification)
    environs.extend(specified_environs)

    environs.append(f"METISA_RUN_ID={sandbox_context.run_identifier}")

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="warden",
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
            "-m",
            "uvicorn",
            f"{MCP_SERVER_MODULE_NAME}.server:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(_MCP_SERVER_PORT),
        ]
    )

    create_docker_container(arguments)

    if len(container_creation_context.network_names) > 1:
        for network_name in container_creation_context.network_names[1:]:
            connect_container_to_docker_network(
                container_name=container_name,
                network_name=network_name,
                aliases=(_MCP_SERVER_NETWORK_ALIAS,),
            )

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("MCP Server sidecar failed to start.")

    return ContainerCreationResult(container_name, staged_source=staged_source_path)


def _ensure_mcp_server_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_MCP_SERVER_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_mcp_server_image(specification, image_reference)
    return image_reference


def _create_mcp_server_container_name(
    run_identifier: str,
) -> str:
    return f"mcp-server-{run_identifier}"


def _create_mcp_server_image(
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
    if specification.mcp_server is None:
        raise RuntimeError("Specification did not contain an [mcp_server] table.")
    collection: list[str] = list(specification.mcp_server.tools)
    collection.extend(list(specification.mcp_server.resources))
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"


def _create_metisa_json(mcp_specification: McpServerSpecification) -> str:
    tools = [tool for tool in mcp_specification.tools]
    resources = [resource for resource in mcp_specification.resources]
    config = {
        "tools": tools,
        "resources": resources,
    }
    return json.dumps(config, indent=2)
