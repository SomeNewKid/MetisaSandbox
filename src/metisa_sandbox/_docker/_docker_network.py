"""Provides utility methods for Docker network management."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence

from ._docker_engine import get_docker_command_location


def create_docker_network(
    network_name: str,
    *,
    internal: bool = False,
) -> None:
    """Create a Docker network."""
    docker_command_location = get_docker_command_location()

    arguments = [
        docker_command_location,
        "network",
        "create",
    ]

    if internal:
        arguments.extend(
            [
                "--internal",
            ]
        )

    arguments.extend([network_name])

    result = subprocess.run(
        args=arguments,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        message = f"Could not create Docker network '{network_name}'\n{output}"
        raise RuntimeError(message)


def connect_container_to_docker_network(
    container_name: str,
    network_name: str,
    *,
    aliases: Sequence[str] = (),
) -> None:
    """Connect the named container to the named Docker network."""
    docker_command_location = get_docker_command_location()

    arguments = [
        docker_command_location,
        "network",
        "connect",
    ]

    if aliases:
        for alias in aliases:
            arguments.extend(["--alias", alias])

    arguments.extend(
        [
            network_name,
            container_name,
        ]
    )

    result = subprocess.run(
        args=arguments,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        message = (
            f"Could not attach container '{container_name}' "
            f"to Docker network '{network_name}'\n{output}"
        )
        raise RuntimeError(message)


def get_docker_container_ip_address(
    container_name: str,
    network_name: str,
) -> str:
    """Return the container's IP address on the specified network."""
    docker_command_location = get_docker_command_location()

    arguments = [
        docker_command_location,
        "inspect",
        "--type",
        "container",
        "--format",
        "{{json .NetworkSettings.Networks}}",
        container_name,
    ]

    result = subprocess.run(
        args=arguments,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Could not inspect container '{container_name}'\n{output}")

    networks = json.loads(result.stdout)
    network = networks.get(network_name)
    if network is None:
        raise RuntimeError(
            f"Container '{container_name}' is not attached to network '{network_name}'."
        )

    address = network.get("IPAddress")
    if not isinstance(address, str) or not address:
        raise RuntimeError(
            f"Container '{container_name}' has no IPv4 address "
            f"on network '{network_name}'."
        )

    return address


def remove_docker_network(
    network_name: str,
) -> None:
    """Remove the named Docker network."""
    docker_command_location = get_docker_command_location()

    arguments = [
        docker_command_location,
        "network",
        "rm",
        network_name,
    ]

    result = subprocess.run(
        args=arguments,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        message = f"Could not remove Docker network '{network_name}':\n{output}"
        raise RuntimeError(message)
