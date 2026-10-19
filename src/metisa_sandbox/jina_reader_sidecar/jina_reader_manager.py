"""Manage a Jina Reader sidecar."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    get_resolved_environs_for_jina_reader,
)
from metisa_common.specification_models import MetisaSpecification

from ..docker.docker_container import (
    create_docker_container,
    inspect_docker_container,
    start_docker_container,
)
from ..docker.docker_hardening import (
    configure_http_proxy,
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
_JINA_READER_ALIAS = "metisa-jina-reader"
_JINA_READER_IMAGE_NAME = "metisa-jina-reader"
_USE_SQUID_PROXY = True


def create_jina_reader_definition() -> SandboxContainer:
    """Return the definition of the Jina Reader container."""
    return SandboxContainer(
        "Jina Reader",
        "jina_reader",
        log_folder="jina-reader",
        log_files=[],
    )


def create_jina_reader_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create the Jina Reader container and connect it to the Docker network."""
    image_name = _ensure_jina_reader_image_exists(specification)
    container_name = _create_jina_reader_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the Jina Reader container.")
    network_name = container_creation_context.network_names[0]

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
        "--network-alias",
        _JINA_READER_ALIAS,
    ]

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/tmp:rw,size=64m,nosuid,nodev,noexec",
        ]
    )

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/home/jina:rw,size=64m,nosuid,nodev,noexec,mode=0700,uid=1001,gid=997",
        ]
    )

    # Configure use of Squid Proxy
    squid_proxy_url = container_creation_context.squid_proxy_url
    if _USE_SQUID_PROXY:
        configure_http_proxy(environs, squid_proxy_url)

    specified_environs = get_resolved_environs_for_jina_reader(specification)
    environs.extend(specified_environs)

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="surfer",
        memory="1g",
        cpu_count=2,
        number_container_processes=512,
        file_size_limit=None,
        number_of_files=1024,
        health_start_seconds=120,
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
        raise RuntimeError("Jina Reader sidecar failed to start.")

    return ContainerCreationResult(container_name)


def _ensure_jina_reader_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_JINA_READER_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_jina_reader_image(specification, image_reference)
    return image_reference


def _create_jina_reader_container_name(
    run_identifier: str,
) -> str:
    return f"jina-reader-{run_identifier}"


def _create_jina_reader_image(
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
