"""Provides utility methods for Docker container management."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

from .docker_engine import get_docker_command_location


def create_docker_container(
    arguments: Sequence[str],
) -> None:
    """Create a Docker container."""
    docker_command_location = get_docker_command_location()

    command = [docker_command_location, "create"]

    for arg in arguments:
        command.append(arg)

    result = subprocess.run(
        args=command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        message = f"Could not create Docker container:\n{output}"
        raise RuntimeError(message)


def run_docker_container(arguments: Sequence[str], *, interactive: bool = False) -> int:
    """Run a Docker container."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "run",
    ]

    if arguments:
        for arg in arguments:
            command.append(arg)

    if interactive:  # no streaming
        process = subprocess.Popen(
            command,
            text=True,
        )

        return process.wait()

    # streaming

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=0,
    )

    if process.stdout is not None:
        while True:
            chunk = process.stdout.read(1)
            if chunk == "":
                break

            print(chunk, end="", flush=True)

    return process.wait()
