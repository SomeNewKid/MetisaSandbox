"""Orchestrate and manage the Docker sandbox."""

from __future__ import annotations

from pathlib import Path

from metisa_common.models import Capability, MetisaSpecification

from .docker.docker_container import run_docker_container
from .metisa_container.metisa_container_manager import create_docker_run_arguments
from .metisa_container.metisa_container_workspace import (
    clean_up_staged_source,
    create_staged_source_directory,
)
from .run_workspace import (
    append_log_file,
    clean_up_run_directory,
    create_log_file,
    create_sandbox_context,
)
from .sandbox_context import SandboxContext
from .sandbox_network import (
    create_docker_egress_network,
    create_docker_private_network,
    remove_docker_egress_network,
    remove_docker_private_network,
)


def run_workload_in_sandbox(
    specification: MetisaSpecification,
    image_reference: str,
    workload_module: str,
) -> int:
    """Run the specified workload in a Docker sandbox."""
    is_private_network_required = Capability.NETWORK in specification.capabilities
    is_egress_network_required = Capability.INTERNET in specification.capabilities

    sandbox_context: SandboxContext | None = None
    log_file: Path | None = None
    staged_source_path: Path | None = None
    private_network_created = False
    egress_network_created = False
    return_code: int | None = None

    try:
        sandbox_context = create_sandbox_context()
        log_file = create_log_file(sandbox_context, image_reference)

        staged_source_path = create_staged_source_directory(
            sandbox_context, workload_module
        )

        arguments = create_docker_run_arguments(
            specification,
            sandbox_context,
            image_reference,
            staged_source_path,
            workload_module,
            is_private_network_required,
        )

        append_log_file(log_file, [f"Arguments: {' '.join(arguments)}"])

        if is_private_network_required:
            create_docker_private_network(sandbox_context)
            private_network_created = True

        if is_egress_network_required:
            create_docker_egress_network(sandbox_context)
            egress_network_created = True

        is_interactive = Capability.INTERACTIVE in specification.capabilities

        return_code = run_docker_container(arguments, interactive=is_interactive)

        return return_code

    except Exception as error:
        if log_file is not None:
            append_log_file(log_file, [f"Error: {error}"])
        raise

    finally:
        try:
            if private_network_created and sandbox_context is not None:
                remove_docker_private_network(sandbox_context)

            if egress_network_created and sandbox_context is not None:
                remove_docker_egress_network(sandbox_context)

        finally:
            if sandbox_context is not None:
                clean_up_run_directory(
                    sandbox_context.host_run_path,
                    sandbox_context.host_output_path,
                )

            if staged_source_path is not None:
                clean_up_staged_source(staged_source_path)

            if log_file is not None and return_code is not None:
                append_log_file(log_file, [f"Return code: {return_code}"])
