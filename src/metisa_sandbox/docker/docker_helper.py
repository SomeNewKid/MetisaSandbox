"""
Provides utility methods for working with Docker.
"""

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


def docker_image_exists(image_name: str, image_tag: str) -> bool:
    docker_command_location = _get_docker_command_location()
    image_reference = create_image_reference(image_name, image_tag)
    result = subprocess.run(
        [docker_command_location, "image", "inspect", image_reference],
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0


def build_docker_image(image_name: str, image_tag: str) -> bool:
    """Ensure the image is available for the defined Dockerfile"""

    docker_command_location = _get_docker_command_location()

    image_reference = create_image_reference(image_name, image_tag)

    dockerfile_path = _get_dockerfile_location()
    build_context_path = dockerfile_path.parent

    result = subprocess.run(
        [
            docker_command_location,
            "build",
            "-t",
            image_reference,
            "-f",
            str(dockerfile_path),
            str(build_context_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Could not build Docker image.\n{output}")

    return True


def docker_engine_started(timeout_seconds: int = 0) -> bool:

    docker_command_location = _get_docker_command_location()

    if timeout_seconds < 1:
        return _docker_engine_available(docker_command_location)

    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if _docker_engine_available(docker_command_location):
            return True
        time.sleep(5)

    raise RuntimeError("Timed out waiting for Docker Engine to become available.")


def start_docker_desktop() -> None:
    if not _DOCKER_DESKTOP_EXE.exists():
        raise RuntimeError(
            f"Docker Desktop could not be found at {_DOCKER_DESKTOP_EXE}."
        )

    subprocess.Popen(
        [str(_DOCKER_DESKTOP_EXE)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def create_image_reference(image_name: str, image_tag: str) -> str:
    return f"{image_name}:{image_tag}"


def _get_docker_command_location() -> str:
    docker_path = shutil.which("docker")
    if not docker_path:
        raise RuntimeError("Docker command is not available.")
    return docker_path


def _get_dockerfile_location() -> Path:
    dockerfile_location = Path(__file__).with_name("dockerfile")
    if not dockerfile_location.exists():
        raise RuntimeError("Dockerfile is not available.")
    return dockerfile_location


def _docker_engine_available(docker_command_location: str) -> bool:
    docker_command_location = _get_docker_command_location()

    result = subprocess.run(
        [docker_command_location, "info"],
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0
