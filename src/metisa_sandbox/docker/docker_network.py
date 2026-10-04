"""Provides utility methods for Docker network management."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

from .docker_engine import get_docker_command_location


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

    result = subprocess.run(args=arguments, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        message = (
            f"Could not attach container '{container_name}' "
            f"to Docker network '{network_name}'\n{output}"
        )
        raise RuntimeError(message)


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
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        message = f"Could not remove Docker network '{network_name}':\n{output}"
        raise RuntimeError(message)
