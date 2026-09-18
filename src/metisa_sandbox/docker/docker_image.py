"""Provides utility methods for working with Docker images."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .docker_engine import get_docker_command_location


def docker_image_exists(
    image_reference: str,
) -> bool:
    """Check if a Docker image with the specified name and tag exists."""
    docker_command_location = get_docker_command_location()
    result = subprocess.run(
        [docker_command_location, "image", "inspect", image_reference],
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0


def build_docker_image(
    image_reference: str,
) -> bool:
    """Ensure the image is available for the defined Dockerfile."""
    docker_command_location = get_docker_command_location()

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


def create_image_reference(
    image_name: str,
    image_tag: str,
) -> str:
    """Create a Docker image reference from the image name and tag."""
    return f"{image_name}:{image_tag}"


def _get_dockerfile_location() -> Path:
    dockerfile_location = Path(__file__).with_name("dockerfile")
    if not dockerfile_location.exists():
        raise RuntimeError("Dockerfile is not available.")
    return dockerfile_location
