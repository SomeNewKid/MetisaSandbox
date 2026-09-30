"""Provides utility methods for working with Docker images."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from metisa_common.models import MetisaSpecification

from ..docker.docker_image import build_docker_image


def build_metisa_container_image(
    specification: MetisaSpecification,
    image_reference: str,
) -> None:
    """Ensure the image is available for the defined Dockerfile."""
    dockerfile_path = _get_dockerfile_location()
    build_context_path = dockerfile_path.parent

    temporary_dir = tempfile.mkdtemp()
    requirements_file = os.path.join(temporary_dir, "requirements.txt")

    sorted_dependencies: list[str] = sorted(specification.dependencies)
    with open(requirements_file, "w", encoding="utf-8") as file:
        for dependency in sorted_dependencies:
            file.write(dependency)
            file.write("\n")

    if not Path(requirements_file).exists():
        raise RuntimeError("Cannot create temporary requirements.txt file.")

    try:
        build_docker_image(
            image_reference,
            dockerfile_path,
            build_context_path,
            named_build_contexts={"temporary_dir": Path(temporary_dir)},
        )
    finally:
        shutil.rmtree(temporary_dir)


def _get_dockerfile_location() -> Path:
    dockerfile_location = Path(__file__).with_name("dockerfile")
    if not dockerfile_location.exists():
        raise RuntimeError("Dockerfile is not available.")
    return dockerfile_location
