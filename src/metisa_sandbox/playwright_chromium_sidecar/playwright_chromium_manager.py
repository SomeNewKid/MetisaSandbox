"""Manage a Playwright Chromium sidecar."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    resolve_environs,
)
from metisa_common.specification_models import MetisaSpecification

from .._docker._docker_container import (
    create_docker_container,
)
from .._docker._docker_hardening import (
    configure_http_proxy,
    harden_docker_container,
)
from .._docker._docker_image import (
    build_docker_image,
    docker_image_exists,
)
from .._docker._docker_network import (
    connect_container_to_docker_network,
)
from .._sandbox_models import (
    ContainerCreationContext,
    ContainerCreationResult,
    SandboxContainer,
    SandboxContext,
)

_IMAGE_FORMAT_VERSION = 1
_PLAYWRIGHT_CHROMIUM_ALIAS = "metisa-playwright-chromium"
_PLAYWRIGHT_CHROMIUM_IMAGE_NAME = "metisa-playwright-chromium"
_USE_SQUID_PROXY = True


def create_playwright_chromium_definition() -> SandboxContainer:
    """Return the definition of the Playwright Chromium container."""
    return SandboxContainer(
        "Playwright Chromium",
        "playwright_chromium",
        log_folder="playwright-chromium",
        log_files=[],
    )


def create_playwright_chromium_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create the Playwright Chromium container and connect it to the Docker network."""
    run_identifier = sandbox_context.run_identifier
    image_name = _ensure_playwright_chromium_image_exists(specification)
    container_name = _create_playwright_chromium_container_name(run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError(
            "No network specified for the Playwright Chromium container."
        )
    network_name = container_creation_context.network_names[0]

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
        "--network-alias",
        _PLAYWRIGHT_CHROMIUM_ALIAS,
    ]

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/tmp:rw,size=64m,nosuid,nodev,noexec",
        ]
    )

    # Configure use of Squid Proxy
    squid_proxy_url = container_creation_context.squid_proxy_url
    if _USE_SQUID_PROXY:
        configure_http_proxy(environs, squid_proxy_url)

    # Get environment variables
    if specification.playwright_chromium is not None:
        resolved_environs = resolve_environs(specification.playwright_chromium.environs)
        environs.extend(resolved_environs)

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="browser",
        memory="512m",
        number_container_processes=256,
        file_size_limit=8 * 1024 * 1024,
        seccomp_path=Path(__file__).resolve().with_name("seccomp.json"),
        health_start_seconds=360,
    )

    # The image name must be specified last in the arguments list.
    arguments.extend(
        [
            image_name,
        ]
    )

    create_docker_container(arguments)

    if len(container_creation_context.network_names) > 1:
        for network_name in container_creation_context.network_names[1:]:
            connect_container_to_docker_network(
                container_name=container_name,
                network_name=network_name,
                aliases=(_PLAYWRIGHT_CHROMIUM_ALIAS,),
            )

    return ContainerCreationResult(container_name)


def _ensure_playwright_chromium_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_PLAYWRIGHT_CHROMIUM_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_playwright_chromium_image(specification, image_reference)
    return image_reference


def _create_playwright_chromium_container_name(
    run_identifier: str,
) -> str:
    return f"playwright-chromium-{run_identifier}"


def _create_playwright_chromium_image(
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
