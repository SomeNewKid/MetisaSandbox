"""Provides utility methods for Docker network management."""

from __future__ import annotations

import subprocess

from .docker_engine import get_docker_command_location


def create_docker_network(network_name: str, *, internal: bool = False) -> None:
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
