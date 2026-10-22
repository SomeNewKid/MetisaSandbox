"""Provides utility methods for Docker container management."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path

from ._docker_engine import get_docker_command_location
from ._docker_hardening import HARDENING_LABEL


def create_docker_container(
    arguments: Sequence[str],
) -> None:
    """Create a Docker container."""
    if HARDENING_LABEL not in arguments:
        raise RuntimeError("Docker creation arguments have not been hardened.")

    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "create",
    ]

    for arg in arguments:
        command.append(arg)

    _run_command(command, "Could not create Docker container")


def run_docker_container(
    container_name: str,
) -> int:
    """Run a Docker container."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "start",
        "--attach",
        "--interactive",
        container_name,
    ]

    process = subprocess.Popen(
        command,
        text=True,
    )

    return process.wait()


def start_docker_container(
    container_name: str,
    arguments: Sequence[str] | None = None,
) -> None:
    """Start the named Docker container."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "start",
    ]

    if arguments:
        for arg in arguments:
            command.append(arg)

    command.append(container_name)

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

    # Jina Reader can be very slow to start.
    # LLM Servers can be very slow to start.
    deadline = time.monotonic() + 600
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

        time.sleep(attempt * 1)
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


def get_docker_container_inspection(
    container_name: str,
) -> str:
    """Get the inspection data for the named Docker container."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "container",
        "inspect",
        container_name,
    ]

    result = _run_command(
        command,
        f"Could not inspect container '{container_name}'",
    )

    return result.stdout


def get_docker_container_state(
    container_name: str,
) -> str:
    """Get the state data for the named Docker container."""
    docker_command_location = get_docker_command_location()

    command = [
        docker_command_location,
        "inspect",
        "--format",
        "{{json .State}}",
        container_name,
    ]

    result = _run_command(
        command,
        f"Could not get container state '{container_name}'",
    )

    return result.stdout


def execute_docker_command(
    arguments: Sequence[str],
) -> tuple[int, str]:
    """Run a command inside the named Docker container."""
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
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    output = result.stderr.strip() or result.stdout.strip()
    return result.returncode, output


def copy_container_file_to_host_file(
    container_name: str,
    container_file: str,
    host_file: str,
) -> None:
    """Copy a file from the container to the host."""
    docker_command_location = get_docker_command_location()

    Path(host_file).parent.mkdir(parents=True, exist_ok=True)

    command = [
        docker_command_location,
        "container",
        "cp",
        f"{container_name}:{container_file}",
        host_file,
    ]

    _run_command(
        command, f"Could not copy file '{container_file}' from '{container_name}'"
    )


def copy_container_files_to_host_folder(
    container_name: str,
    container_files: list[str],
    host_folder: str,
) -> None:
    """Copy listed files from the container to the host."""
    for container_file in container_files:
        filename = container_file.split("/")[-1]
        if not filename:
            raise ValueError(f"Container file not valid: {container_file}")
        copy_container_file_to_host_file(
            container_name, container_file, str(Path(host_folder) / filename)
        )


def _run_command(
    command: list[str],
    error_message_prefix: str = "An error occurred",
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args=command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{error_message_prefix}:\n{output}")

    return result
