"""Manage an HAProxy sidecar."""

from __future__ import annotations

import os
import shutil
import tempfile
import textwrap
from pathlib import Path

from metisa_common.specification_helper import generate_image_tag
from metisa_common.specification_models import MetisaSpecification

from .._docker._docker_container import (
    create_docker_container,
    execute_docker_command,
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
from .._docker._docker_network import (
    connect_container_to_docker_network,
)
from .._sandbox_models import (
    ContainerCreationContext,
    ContainerCreationResult,
    SandboxContainer,
    SandboxContext,
)

_IMAGE_FORMAT_VERSION = 1
_HAPROXY_ALIAS = "metisa-haproxy"
_HAPROXY_PORT = 8404
_HAPROXY_IMAGE_NAME = "metisa-haproxy"


def create_haproxy_definition() -> SandboxContainer:
    """Return the definition of the HAProxy container."""
    return SandboxContainer(
        "HAProxy",
        "haproxy",
        log_folder="haproxy",
        log_files=["/etc/haproxy/haproxy.cfg"],
    )


def create_haproxy_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create the HAProxy container and connect it to the Docker networks."""
    image_name = _ensure_haproxy_image_exists(specification)
    container_name = _create_haproxy_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the HAProxy container.")
    network_name = container_creation_context.network_names[0]
    mcp_server_ip_address = container_creation_context.mcp_server_ip_address

    haproxy_cfg_file = os.path.join(sandbox_context.host_scratch_path, "haproxy.cfg")
    haproxy_cfg_contents = _create_haproxy_cfg(specification, mcp_server_ip_address)
    with open(haproxy_cfg_file, "w", encoding="utf-8") as file:
        file.write(haproxy_cfg_contents)

    if not Path(haproxy_cfg_file).exists():
        raise RuntimeError("Could not create haproxy.cfg file for HAProxy.")

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
    ]

    if _use_network_alias(sandbox_context, network_name):
        arguments.extend(
            [
                "--network-alias",
                _HAPROXY_ALIAS,
            ]
        )

    # If MCP Server is deployed, overwrite the haproxy.cfg
    if mcp_server_ip_address is not None:
        arguments.extend(
            [
                "--mount",
                (
                    "type=bind,"
                    f"source={haproxy_cfg_file},"
                    "target=/etc/haproxy/haproxy.cfg,"
                    "readonly"
                ),
            ]
        )

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/tmp:rw,size=16m,nosuid,nodev,noexec",
        ]
    )

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=[],
        username="haproxy",
        cpu_count=1,
        memory="128m",
        number_of_files=512,
    )

    # The image name must be specified last in the arguments list.
    arguments.extend(
        [
            image_name,
        ]
    )

    create_docker_container(arguments)

    if len(container_creation_context.network_names) > 1:
        for network_name in container_creation_context.network_names[1:]:
            if _use_network_alias(sandbox_context, network_name):
                connect_container_to_docker_network(
                    container_name=container_name,
                    network_name=network_name,
                    aliases=(_HAPROXY_ALIAS,),
                )
            else:
                connect_container_to_docker_network(
                    container_name=container_name,
                    network_name=network_name,
                )

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("HAProxy sidecar failed to start.")

    _verify_haproxy_configuration(container_name)

    return ContainerCreationResult(container_name)


def _use_network_alias(
    sandbox_context: SandboxContext,
    network_name: str,
) -> bool:
    if network_name == sandbox_context.egress_network_name:
        return False
    return True


# Verify HAProxy configuration inside the container.
# This must be done after the container is attached to the network and started,
# because the configuration file may include an instruction like this:
#
#   frontend listener_3306
#       bind ipv4@metisa-haproxy:3306
#       mode tcp
#       default_backend destination_3306
#
# The metisa-haproxy host name must be resolved by the container's DNS,
# which is not available during image building or container creation.
def _verify_haproxy_configuration(
    container_name: str,
) -> None:
    """Verify the HAProxy configuration inside the container."""
    exitcode, message = execute_docker_command(
        [container_name, "haproxy", "-c", "-f", "/etc/haproxy/haproxy.cfg"]
    )
    if exitcode != 0:
        raise RuntimeError(f"HAProxy configuration verification failed: {message}")


def _ensure_haproxy_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_HAPROXY_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_haproxy_image(specification, image_reference)
    return image_reference


def _create_haproxy_container_name(
    run_identifier: str,
) -> str:
    return f"metisa-haproxy-{run_identifier}"


def _create_haproxy_image(
    specification: MetisaSpecification,
    image_reference: str,
) -> None:
    dockerfile_location = _get_dockerfile_location()
    build_context_path = dockerfile_location.parent

    temporary_dir = tempfile.mkdtemp()
    haproxy_cfg_file = os.path.join(temporary_dir, "haproxy.cfg")
    haproxy_cfg_contents = _create_haproxy_cfg(specification)
    with open(haproxy_cfg_file, "w", encoding="utf-8") as file:
        file.write(haproxy_cfg_contents)

    if not Path(haproxy_cfg_file).exists():
        raise RuntimeError("Could not create haproxy.cfg file for HAProxy.")

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
    if specification.haproxy is None:
        raise RuntimeError("Specification did not contain an [haproxy] table.")
    collection: list[str] = []
    for backend in specification.haproxy.backends:
        collection.append(f"{backend.listen_port}|{backend.host}|{backend.port}")
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"


# The following `metisa.toml` fragment:
#
#     [haproxy]
#     backends = [
#        { listen_port = 3306, host = "host.docker.internal", port = 3306 },
#     ]
#
# should produce the following skeletal `haproxy.cfg` file:
#
#   frontend listener_3306
#       bind :3306
#       mode tcp
#       default_backend destination_3306
#
#   backend destination_3306
#       mode tcp
#       server database host.docker.internal:3306 check
#
def _create_haproxy_cfg(
    specification: MetisaSpecification,
    mcp_server_ip_address: str | None = None,
) -> str:
    if not specification.haproxy:
        return ""

    backends = specification.haproxy.backends

    instructions: list[str] = []

    inactivity_timeout_seconds = 120
    finish_timeout_seconds = 60

    instructions.append(
        textwrap.dedent(
            """
        global
            # maximum number of concurrent connections
            maxconn 64
            log stdout format raw local0
        """
        ).strip()
    )

    instructions.append(
        textwrap.dedent(
            f"""
        defaults
            retries 3
            # maximum time to wait for a successful TCP connection to backend server
            timeout connect 5s

             # maximum inactivity time on the client side
            timeout client {inactivity_timeout_seconds}s
            timeout client-fin {finish_timeout_seconds}s

            # maximum inactivity time on the backend server side
            timeout server {inactivity_timeout_seconds}s
            timeout server-fin {finish_timeout_seconds}s
        """
        ).strip()
    )

    # Loopback-only HTTP monitoring frontend
    # used by HEALTHCHECK in dockerfile.
    instructions.append(
        textwrap.dedent(
            f"""
        frontend appliance_health
            bind 127.0.0.1:{_HAPROXY_PORT}
            mode http
            monitor-uri /health
        """
        ).strip()
    )

    for backend in backends:
        listener_instructions = [
            f"frontend listener_{backend.listen_port}",
            f"    bind ipv4@metisa-haproxy:{backend.listen_port}",
            "    mode tcp",
            "    log global",
            "    option tcplog",
        ]

        if mcp_server_ip_address is not None:
            listener_instructions.extend(
                [
                    f"    acl mcp_server src {mcp_server_ip_address}",
                    "    tcp-request connection reject unless mcp_server",
                ]
            )

        listener_instructions.extend(
            [
                f"    default_backend destination_{backend.listen_port}",
                "",
                f"backend destination_{backend.listen_port}",
                "    mode tcp",
                f"    server database {backend.host}:{backend.port} check",
            ]
        )

        listener_configuration = "\n".join(listener_instructions)
        instructions.append(listener_configuration)

    final_linefeed_required_by_haproxy = "\n"
    return "\n\n".join(instructions) + final_linefeed_required_by_haproxy
