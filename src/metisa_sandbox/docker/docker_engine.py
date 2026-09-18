"""Provides utility methods for Docker availability and Docker Desktop management."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

_DOCKER_DESKTOP_EXE = (
    Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
    / "Docker"
    / "Docker"
    / "Docker Desktop.exe"
)


def docker_engine_started(
    timeout_seconds: int = 0,
) -> bool:
    """Check if the Docker Engine has started within the given timeout."""
    docker_command_location = get_docker_command_location()

    if timeout_seconds < 1:
        return _docker_engine_available(docker_command_location)

    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if _docker_engine_available(docker_command_location):
            return True
        time.sleep(5)

    raise RuntimeError("Timed out waiting for Docker Engine to become available.")


def start_docker_desktop() -> None:
    """Start Docker Desktop if it is installed."""
    if not _DOCKER_DESKTOP_EXE.exists():
        raise RuntimeError(
            f"Docker Desktop could not be found at {_DOCKER_DESKTOP_EXE}."
        )

    subprocess.Popen(
        [str(_DOCKER_DESKTOP_EXE)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def get_docker_command_location() -> str:
    """Get the location of the Docker command."""
    docker_path = shutil.which("docker")
    if not docker_path:
        raise RuntimeError("Docker command is not available.")
    return docker_path


def _docker_engine_available(
    docker_command_location: str,
) -> bool:
    """Check if the Docker Engine is available using the specified Docker command."""
    result = subprocess.run(
        [docker_command_location, "info"],
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0
