"""Provides utility methods for Docker container management."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Sequence

from .docker_engine import get_docker_command_location


def create_docker_container(
    arguments: Sequence[str],
) -> None:
    """Create a Docker container."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "create",
    ]

    for arg in arguments:
        command.append(arg)

    _run_command(command, "Could not create Docker container")


def run_docker_container(
    arguments: Sequence[str],
    *,
    interactive: bool = False,
) -> int:
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


def start_docker_container(
    container_name: str,
) -> None:
    """Start the named Docker container."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "start",
        container_name,
    ]

    _run_command(command, f"Could not start Docker container '{container_name}'")


def stop_docker_container(
    container_name: str,
    timeout_seconds: int = 30,  # Docker's default timeout
) -> None:
    """Stop the named Docker container."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "container",
        "stop",
        "--time",
        str(timeout_seconds),
        container_name,
    ]

    _run_command(command, f"Could not stop Docker container '{container_name}'")


def remove_docker_container(container_name: str, force: bool = False) -> None:
    """Remove the named Docker container."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "container",
        "rm",
    ]

    if force:
        command.extend(
            [
                "--force",
            ]
        )

    command.extend(
        [
            container_name,
        ]
    )

    _run_command(command, f"Could not remove Docker container '{container_name}'")


def inspect_docker_container(
    container_name: str,
) -> bool:
    """Inspect the named Docker container and return its JSON output."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "inspect",
        "--format",
        "{{json .State}}",
        container_name,
    ]

    deadline = time.monotonic() + 30
    attempt = 1

    while time.monotonic() < deadline:
        result = _run_command(
            command, f"Could not inspect Docker container '{container_name}'"
        )

        output = result.stdout.strip()

        state = json.loads(output)

        state_running = state.get("Running")
        if not state_running:
            return False

        state_health = state.get("Health", {})

        state_health_status = state_health.get("Status")

        if state_health_status == "healthy":
            return True
        if state_health_status == "unhealthy":
            return False

        time.sleep(attempt * 0.25)
        attempt += 1

    return False


def get_docker_container_logs(
    container_name: str,
) -> tuple[str, str]:
    """Get the stdout,stderr logs for named Docker container."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "container",
        "logs",
        "--timestamps",
        container_name,
    ]

    result = _run_command(
        command, f"Could not get logs for Docker container '{container_name}'"
    )

    return result.stdout, result.stderr


def execute_docker_command(
    arguments: Sequence[str],
) -> tuple[int, str]:
    """
    Run a command inside the named Docker container and 
    return its exit code and output message.
    """
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "exec",
    ]

    for arg in arguments:
        command.append(arg)

    result = subprocess.run(
        args=command,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stderr.strip() or result.stdout.strip()
    return result.returncode, output


def _run_command(
    command: list[str],
    error_message_prefix: str = "An error occurred",
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args=command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{error_message_prefix}:\n{output}")

    return result
