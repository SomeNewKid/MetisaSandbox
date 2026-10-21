"""Manage a OpenTelemetry Collector sidecar."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    get_resolved_environs_for_otel_collector,
)
from metisa_common.specification_models import MetisaSpecification

from ..docker.docker_container import (
    create_docker_container,
    inspect_docker_container,
    start_docker_container,
)
from ..docker.docker_hardening import (
    harden_docker_container,
)
from ..docker.docker_image import (
    build_docker_image,
    docker_image_exists,
)
from ..sandbox_models import (
    ContainerCreationContext,
    ContainerCreationResult,
    SandboxContainer,
    SandboxContext,
)

_IMAGE_FORMAT_VERSION = 1
_OTEL_COLLECTOR_ALIAS = "metisa-otel-collector"
_OTEL_COLLECTOR_IMAGE_NAME = "metisa-otel-collector"


def create_otel_collector_definition() -> SandboxContainer:
    """Return the definition of the OpenTelemetry Collector container."""
    return SandboxContainer(
        "OpenTelemetry Collector",
        "otel_collector",
        log_folder="otel-collector",
        log_files=[],
    )


def create_otel_collector_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create and start a OpenTelemetry Collector sidecar container."""
    image_name = _ensure_otel_collector_image_exists(specification)
    container_name = _create_otel_collector_container_name(
        sandbox_context.run_identifier
    )

    if not container_creation_context.network_names:
        error = "No network specified for the OpenTelemetry Collector container."
        raise RuntimeError(error)
    network_name = container_creation_context.network_names[0]

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
        "--network-alias",
        _OTEL_COLLECTOR_ALIAS,
    ]

    # Create the telemetry directory on the host and mount it into the container.
    telemetry_path = sandbox_context.host_logs_path / "telemetry"
    telemetry_path.mkdir(parents=True, exist_ok=True)

    arguments.extend(
        [
            "--mount",
            f"type=bind,source={telemetry_path},target=/telemetry",
        ]
    )

    specified_environs = get_resolved_environs_for_otel_collector(specification)
    environs.extend(specified_environs)

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="collector",
        health_start_seconds=30,
    )

    # The image name must be specified last in the arguments list.
    arguments.extend(
        [
            image_name,
        ]
    )

    create_docker_container(arguments)

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("OpenTelemetry Collector sidecar failed to start.")

    return ContainerCreationResult(container_name)


def _ensure_otel_collector_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_OTEL_COLLECTOR_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_otel_collector_image(specification, image_reference)
    return image_reference


def _create_otel_collector_container_name(
    run_identifier: str,
) -> str:
    return f"otel-collector-{run_identifier}"


def _create_otel_collector_image(
    specification: MetisaSpecification,
    image_reference: str,
) -> None:
    dockerfile_location = _get_dockerfile_location()
    build_context_path = dockerfile_location.parent

    build_docker_image(
        image_reference=image_reference,
        dockerfile_path=dockerfile_location,
        build_context_path=build_context_path,
    )


def _get_dockerfile_location() -> Path:
    dockerfile_location = Path(__file__).with_name("dockerfile")
    if not dockerfile_location.exists():
        raise RuntimeError("Dockerfile is not available.")
    return dockerfile_location


def _generate_image_tag(
    specification: MetisaSpecification,
) -> str:
    collection: list[str] = []
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"
