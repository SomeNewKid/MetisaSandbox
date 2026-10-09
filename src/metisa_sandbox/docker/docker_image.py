"""Provides utility methods for Docker image management."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
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
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    return result.returncode == 0


def build_docker_image(
    image_reference: str,
    dockerfile_path: Path,
    build_context_path: Path,
    *,
    named_build_contexts: Mapping[str, Path] | None = None,
) -> None:
    """Build a Docker image using the specified Dockerfile and build context."""
    docker_command_location = get_docker_command_location()

    arguments = [
        docker_command_location,
        "build",
    ]

    if named_build_contexts:
        for name, path in named_build_contexts.items():
            arguments.extend(["--build-context", f"{name}={str(path)}"])

    arguments.extend(
        [
            "--tag",
            image_reference,
            "--file",
            str(dockerfile_path),
            str(build_context_path),
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
        raise RuntimeError(f"Could not build Docker image.\n{output}")


def create_image_reference(
    image_name: str,
    image_tag: str,
) -> str:
    """Create a Docker image reference from the image name and tag."""
    return f"{image_name}:{image_tag}"
