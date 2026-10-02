"""Orchestrate and manage the Docker sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

from metisa_common.specification_models import Capability, MetisaSpecification

from .docker.docker_container import (
    get_docker_container_logs,
    remove_docker_container,
    run_docker_container,
    stop_docker_container,
)
from .metisa_container.metisa_container_manager import (
    create_docker_run_arguments,
)
from .metisa_container.metisa_container_workspace import (
    clean_up_staged_source,
    create_staged_source_directory,
)
from .sandbox_context import (
    SandboxContext,
)
from .sandbox_network import (
    create_docker_egress_network,
    create_docker_private_network,
    remove_docker_egress_network,
    remove_docker_private_network,
)
from .sandbox_workspace import (
    append_log_file,
    clean_up_run_directory,
    create_log_file,
    create_sandbox_context,
)
from .squid_proxy_container.squid_proxy_manager import (
    create_squid_proxy_container,
    get_squid_proxy_url,
)


def run_metisa_container_workload_in_sandbox(
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
    squid_proxy_container_name: str | None = None
    squid_proxy_url: str | None = None

    if is_egress_network_required:
        squid_proxy_url = get_squid_proxy_url()

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
            squid_proxy_url,
        )

        append_log_file(log_file, [f"Arguments: {' '.join(arguments)}"])

        if is_private_network_required:
            print("Creating private network.")
            create_docker_private_network(sandbox_context)
            private_network_created = True
            print("Created private network.")

        if is_egress_network_required:
            print("Creating egress network.")
            create_docker_egress_network(sandbox_context)
            egress_network_created = True
            squid_proxy_container_name = create_squid_proxy_container(
                specification, sandbox_context
            )
            print("Created egress network.")

        is_interactive = Capability.INTERACTIVE in specification.capabilities

        return_code = run_docker_container(arguments, interactive=is_interactive)

        return return_code

    except Exception as error:
        if log_file is not None:
            append_log_file(log_file, [f"Error: {error}"])
        raise

    finally:
        try:
            print("Cleaning up environment.")
            cleanup_errors: list[str] = []

            if squid_proxy_container_name is not None:
                squid_stopped = False

                try:
                    print("Stopping Squid Proxy container.")
                    stop_docker_container(
                        squid_proxy_container_name, timeout_seconds=10
                    )
                    squid_stopped = True
                    print("Stopped Squid Proxy container.")
                except Exception as error:
                    print("Could not stop Squid Proxy container.")
                    cleanup_errors.append(
                        f"Could not stop Squid Proxy container: {error}"
                    )

                try:
                    _save_container_logs(
                        sandbox_context, squid_proxy_container_name, "squid_proxy"
                    )
                except Exception as error:
                    cleanup_errors.append(f"Could not save Squid Proxy logs: {error}")

                try:
                    print("Removing Squid Proxy container.")
                    remove_docker_container(
                        squid_proxy_container_name, force=not squid_stopped
                    )
                    print("Removed Squid Proxy container.")
                except Exception as error:
                    print("Could not rempve Squid Proxy container.")
                    cleanup_errors.append(
                        f"Could not remove Squid Proxy container: {error}"
                    )

            if egress_network_created and sandbox_context is not None:
                try:
                    print("Removing egress network.")
                    remove_docker_egress_network(sandbox_context)
                    print("Removed egress network.")
                except Exception as error:
                    cleanup_errors.append(f"Could not remove egress network: {error}")

            if private_network_created and sandbox_context is not None:
                try:
                    print("Removing private network.")
                    remove_docker_private_network(sandbox_context)
                    print("Removed private network.")
                except Exception as error:
                    cleanup_errors.append(f"Could not remove private network: {error}")

            for cleanup_error in cleanup_errors:
                try:
                    if log_file is not None:
                        append_log_file(log_file, [cleanup_error])
                    else:
                        print(cleanup_error, file=sys.stderr)
                except Exception:
                    print(cleanup_error, file=sys.stderr)

        finally:
            if sandbox_context is not None:
                clean_up_run_directory(
                    sandbox_context.host_output_path,
                    sandbox_context.host_logs_path,
                )

            if staged_source_path is not None:
                clean_up_staged_source(staged_source_path)

            if log_file is not None and return_code is not None:
                append_log_file(log_file, [f"Return code: {return_code}"])

            print("Cleaned up environment.")


def _save_container_logs(
    sandbox_context: SandboxContext | None,
    container_name: str,
    target_dir_name: str,
) -> None:
    if sandbox_context is None:
        return
    target_log_dir = sandbox_context.host_logs_path / target_dir_name
    stdout, stderr = get_docker_container_logs(container_name)
    _save_log_file(target_log_dir / "stdout.txt", stdout)
    _save_log_file(target_log_dir / "stderr.txt", stderr)


def _save_log_file(
    target_file: Path,
    content: str,
) -> None:
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with target_file.open("w", encoding="utf-8") as file:
        file.write(content)
