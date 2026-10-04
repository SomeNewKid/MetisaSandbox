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
from .haproxy_sidecar.haproxy_manager import (
    create_haproxy_container,
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
from .squid_proxy_sidecar.squid_proxy_manager import (
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
    is_internet_access_required = Capability.INTERNET in specification.capabilities
    is_localnet_access_required = Capability.LOCALNET in specification.capabilities
    is_egress_network_required = (
        is_internet_access_required or is_localnet_access_required
    )

    sandbox_context: SandboxContext | None = None
    log_file: Path | None = None
    staged_source_path: Path | None = None
    private_network_created = False
    egress_network_created = False
    return_code: int | None = None
    squid_proxy_container_name: str | None = None
    squid_proxy_url: str | None = None
    haproxy_container_name: str | None = None

    if is_internet_access_required:
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
            print("Created egress network.")

            if is_internet_access_required:
                print("Creating Squid Proxy container.")
                squid_proxy_container_name = create_squid_proxy_container(
                    specification, sandbox_context
                )
                print("Created Squid Proxy container.")

            if is_localnet_access_required:
                print("Creating HAProxy container.")
                haproxy_container_name = create_haproxy_container(
                    specification, sandbox_context
                )
                print("Created HAProxy container.")

        is_interactive = Capability.INTERACTIVE in specification.capabilities

        return_code = run_docker_container(arguments, interactive=is_interactive)

        return return_code

    except Exception as error:
        if log_file is not None:
            append_log_file(log_file, [f"Error: {error}"])
        raise

    finally:
        if sandbox_context is not None:
            try:
                print("Cleaning up environment.")
                cleanup_errors: list[str] = []

                if squid_proxy_container_name is not None:
                    _stop_and_remove_squid_proxy_container(
                        sandbox_context, cleanup_errors, squid_proxy_container_name
                    )

                if haproxy_container_name is not None:
                    _stop_and_remove_haproxy_container(
                        sandbox_context,
                        cleanup_errors,
                        haproxy_container_name,
                    )

                if egress_network_created:
                    try:
                        print("Removing egress network.")
                        remove_docker_egress_network(sandbox_context)
                        print("Removed egress network.")
                    except Exception as error:
                        cleanup_error = f"Could not remove egress network: {error}"
                        cleanup_errors.append(cleanup_error)

                if private_network_created:
                    try:
                        print("Removing private network.")
                        remove_docker_private_network(sandbox_context)
                        print("Removed private network.")
                    except Exception as error:
                        cleanup_error = f"Could not remove private network: {error}"
                        cleanup_errors.append(cleanup_error)

                for cleanup_error in cleanup_errors:
                    try:
                        if log_file is not None:
                            append_log_file(log_file, [cleanup_error])
                        else:
                            print(cleanup_error, file=sys.stderr)
                    except Exception:
                        print(cleanup_error, file=sys.stderr)

            finally:
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


def _stop_and_remove_squid_proxy_container(
    sandbox_context: SandboxContext,
    cleanup_errors: list[str],
    squid_proxy_container_name: str,
) -> None:

    _stop_and_remove_container(
        sandbox_context=sandbox_context,
        cleanup_errors=cleanup_errors,
        container_name=squid_proxy_container_name,
        container_title="Squid Proxy",
        log_folder="squid_proxy",
    )


def _stop_and_remove_haproxy_container(
    sandbox_context: SandboxContext,
    cleanup_errors: list[str],
    haproxy_container_name: str,
) -> None:

    _stop_and_remove_container(
        sandbox_context=sandbox_context,
        cleanup_errors=cleanup_errors,
        container_name=haproxy_container_name,
        container_title="HAProxy",
        log_folder="haproxy",
    )


def _stop_and_remove_container(
    sandbox_context: SandboxContext,
    cleanup_errors: list[str],
    container_name: str,
    container_title: str,
    log_folder: str,
) -> None:

    squid_stopped = False

    try:
        print(f"Stopping {container_title} container.")
        stop_docker_container(container_name, timeout_seconds=10)
        squid_stopped = True
        print(f"Stopped {container_title} container.")
    except Exception as error:
        print(f"Could not stop {container_title} container.")
        cleanup_errors.append(f"Could not stop {container_title} container: {error}")

    try:
        _save_container_logs(sandbox_context, container_name, log_folder)
    except Exception as error:
        cleanup_errors.append(f"Could not save {container_title} logs: {error}")

    try:
        print(f"Removing {container_title} container.")
        remove_docker_container(container_name, force=not squid_stopped)
        print(f"Removed {container_title} container.")
    except Exception as error:
        print(f"Could not rempve {container_title} container.")
        cleanup_errors.append(f"Could not remove {container_title} container: {error}")
