"""Provides utility methods for managing the Docker workload container."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import get_resolved_environs_for_metisa
from metisa_common.specification_models import MetisaSpecification
from metisa_sandbox._docker._docker_container import create_docker_container

from .._docker._docker_hardening import (
    configure_http_proxy,
    harden_docker_container,
)
from .._sandbox_models import (
    ContainerCreationContext,
    ContainerCreationResult,
    SandboxContainer,
    SandboxContext,
)
from ._metisa_container_workspace import (
    LANDLOCK_MODULE_NAME,
    create_staged_source_directory,
)

_GUEST_SOURCE_DIR = "/sandbox-source"
_GUEST_OUTPUT_DIR = "/sandbox-output"
_GUEST_WORK_DIR = "/sandbox-work"
_GUEST_PYTHON_VENV = "/opt/metisa-venv"


def create_metisa_workload_definition() -> SandboxContainer:
    """Return the definition of the Metisa workload container."""
    return SandboxContainer(
        "Metisa Workload",
        "metisa_workload",
        log_folder="metisa",
        log_files=[],
    )


def create_metisa_workload_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create the Metisa Workload container and connect it to the Docker network."""
    creation_settings = container_creation_context.settings

    image_reference = creation_settings.get("image_reference", "")
    if not image_reference:
        raise RuntimeError("Metisa Workload requires an image reference.")
    if not isinstance(image_reference, str):
        raise RuntimeError("Metisa Workload image reference must be a string.")

    workload_module = creation_settings.get("workload_module", "")
    if not workload_module:
        raise RuntimeError("Metisa Workload requires a workload_module.")
    if not isinstance(workload_module, str):
        raise RuntimeError("Metisa Workload workload module must be a string.")

    is_network_required = creation_settings.get("is_network_required", None)
    if not is_network_required:
        raise RuntimeError("Metisa Workload requires a network-required flag.")
    if not isinstance(is_network_required, bool):
        raise RuntimeError("Metisa Workload network-required flag must be a bool.")

    use_squid_proxy = creation_settings.get("use_squid_proxy", None)
    if use_squid_proxy is not None and not isinstance(use_squid_proxy, bool):
        raise RuntimeError("Metisa Workload squid-proxy flag must be a bool.")
    if use_squid_proxy is None:
        use_squid_proxy = False

    staged_source_path = create_staged_source_directory(
        sandbox_context, workload_module
    )

    environs: list[str] = []

    # Initialize the list of Docker run arguments.
    arguments = [
        "--name",
        sandbox_context.workload_container_name,
    ]

    # Specify a seccomp (secure computing mode) profile for the container.
    # The seccomp profile defines a set of system calls that the container
    # is allowed to make (that is, it is a whitelist).
    # This custom seccomp profile started as a copy of the default Docker
    # seccomp profile from commit 6fe7deb1b9fb7c0397a4593480d7d22b9ee8caef.
    seccomp_path = Path(__file__).resolve().with_name("seccomp.json")

    # Configure the network settings for the container
    # based on whether a network is required.
    if is_network_required:
        arguments.extend(
            [
                "--network",
                sandbox_context.workload_network_name,
                "--network-alias",
                "metisa-workload",
            ]
        )
        squid_proxy_url = (
            container_creation_context.squid_proxy_url if is_network_required else None
        )
        if use_squid_proxy and squid_proxy_url is not None:
            configure_http_proxy(environs, squid_proxy_url)
    else:
        arguments.extend(
            [
                "--network",
                "none",
            ]
        )

    # Mount the necessary volumes.
    arguments.extend(
        [
            "--volume",
            f"{staged_source_path}:{_GUEST_SOURCE_DIR}:ro",
            "--volume",
            f"{sandbox_context.host_output_path}:{_GUEST_OUTPUT_DIR}:rw",
        ]
    )

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            f"{_GUEST_WORK_DIR}:rw,size=1m,nosuid,nodev,noexec",
            "--tmpfs",
            "/tmp:rw,size=16m,nosuid,nodev,noexec",
        ]
    )

    # Set environment variables for the container.
    environs.extend(
        [
            f"SANDBOX_OUTPUT_DIR={_GUEST_OUTPUT_DIR}",
            "METISA_RUNTIME_ROLE=landlock",
        ]
    )

    # Set the working directory for the container.
    arguments.extend(
        [
            "--workdir",
            _GUEST_SOURCE_DIR,
        ]
    )

    specified_environs = get_resolved_environs_for_metisa(specification)
    environs.extend(specified_environs)

    environs.append(f"METISA_RUN_ID={sandbox_context.run_identifier}")

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="sandbox",
        interactive=True,
        seccomp_path=seccomp_path,
        number_user_processes=64,
    )

    # ---------------- The following switches must be last ----------------

    # The image from which to construct the container.
    arguments.extend(
        [
            image_reference,
        ]
    )

    # The command to execute within the container.
    arguments.extend(
        [
            f"{_GUEST_PYTHON_VENV}/bin/python",
            "-I",  # Run the Python interpreter in isolated, no-bytecode mode
            "-B",  # Don't write .pyc files on import
            "-m",
            LANDLOCK_MODULE_NAME,
            workload_module,
        ]
    )

    create_docker_container(arguments)

    return ContainerCreationResult(
        sandbox_context.workload_container_name,
        staged_source=staged_source_path,
    )
