"""Utility functions for managing a Docker sandbox container."""

from __future__ import annotations

from pathlib import Path

from metisa_common.terminal_helper import (
    terminal_status,
)

from .docker.docker_container import (
    copy_container_files_to_host_folder,
    get_docker_container_inspection,
    get_docker_container_logs,
    remove_docker_container,
    stop_docker_container,
)
from .sandbox_models import (
    SandboxContainer,
    SandboxContext,
)

_LOG_INSPECTION_FILES = False
_ACKNOWLEDGE_INSPECTION_FILES_HAVE_SENSITIVE_DATA = False


def stop_and_remove_containers(
    sandbox_context: SandboxContext,
    cleanup_errors: list[str],
    sandbox_containers: list[SandboxContainer],
) -> None:
    """Stop and remove all specified sandbox containers."""
    for sandbox_container in sandbox_containers:
        _stop_and_remove_container(
            sandbox_context,
            cleanup_errors,
            sandbox_container,
        )


def _stop_and_remove_container(
    sandbox_context: SandboxContext,
    cleanup_errors: list[str],
    sandbox_container: SandboxContainer,
) -> None:
    log_folder = sandbox_container.log_folder
    if not log_folder:
        return
    if not sandbox_container.is_created:
        return
    try:
        _save_files_from_container(
            sandbox_context,
            sandbox_container.instance_name,
            sandbox_container.log_files,
            log_folder,
        )
    except Exception as error:
        cleanup_errors.append(
            f"Could not save config files for '{sandbox_container.name}': {error}"
        )
    finally:
        _finalize_and_stop_and_remove_container(
            sandbox_context=sandbox_context,
            cleanup_errors=cleanup_errors,
            container_instance_name=sandbox_container.instance_name,
            container_title=sandbox_container.title,
            log_folder=log_folder,
        )


def _save_container_log_files(
    sandbox_context: SandboxContext | None,
    container_name: str,
    target_dir_name: str,
) -> None:
    if sandbox_context is None:
        return
    run_logs_path = sandbox_context.host_logs_path
    run_logs_path.mkdir(parents=True, exist_ok=True)
    target_log_dir = run_logs_path / target_dir_name
    stdout, stderr = get_docker_container_logs(container_name)
    _save_container_log_file(target_log_dir / "stdout.txt", stdout)
    _save_container_log_file(target_log_dir / "stderr.txt", stderr)


def _save_container_log_file(
    target_file: Path,
    content: str,
) -> None:
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with target_file.open("w", encoding="utf-8") as file:
        file.write(content)


def _save_files_from_container(
    sandbox_context: SandboxContext,
    container_name: str,
    container_files: list[str],
    log_folder: str,
) -> None:
    run_logs_path = sandbox_context.host_logs_path
    run_logs_path.mkdir(parents=True, exist_ok=True)
    target_log_dir = run_logs_path / log_folder
    target_log_dir.mkdir(parents=True, exist_ok=True)
    copy_container_files_to_host_folder(
        container_name,
        container_files,
        str(target_log_dir),
    )


def _save_container_inspection(
    sandbox_context: SandboxContext,
    container_name: str,
    target_dir_name: str,
) -> None:
    inspection = get_docker_container_inspection(container_name)
    target_dir = sandbox_context.host_logs_path / target_dir_name
    _save_container_log_file(target_dir / "inspect.json", inspection)


def _finalize_and_stop_and_remove_container(
    sandbox_context: SandboxContext,
    cleanup_errors: list[str],
    container_instance_name: str,
    container_title: str,
    log_folder: str,
) -> None:
    if _LOG_INSPECTION_FILES and _ACKNOWLEDGE_INSPECTION_FILES_HAVE_SENSITIVE_DATA:
        try:
            _save_container_inspection(
                sandbox_context,
                container_instance_name,
                log_folder,
            )
        except Exception as error:
            error_message = f"Could not save {container_title} inspection: {error}"
            cleanup_errors.append(error_message)

    container_stopped = False

    try:
        with terminal_status(
            running=f"Stopping {container_title} container...",
            success=f"Stopped {container_title} container.",
            failure=f"Could not stop {container_title} container.",
        ):
            stop_docker_container(container_instance_name, timeout_seconds=10)
            container_stopped = True
    except Exception as error:
        cleanup_errors.append(f"Could not stop {container_title} container: {error}")

    try:
        _save_container_log_files(sandbox_context, container_instance_name, log_folder)
    except Exception as error:
        cleanup_errors.append(f"Could not save {container_title} logs: {error}")

    try:
        with terminal_status(
            running=f"Removing {container_title} container.",
            success=f"Removed {container_title} container.",
            failure=f"Could not remove {container_title} container.",
        ):
            remove_docker_container(
                container_instance_name, force=not container_stopped
            )
    except Exception as error:
        cleanup_errors.append(f"Could not remove {container_title} container: {error}")
