"""Manages the host filesystem state for a run."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .sandbox_context import SandboxContext


def create_sandbox_context() -> SandboxContext:
    """Create a sandbox context."""
    run_identifier, host_run_directory = _create_run_identifier_and_directory()
    workload_container_name = f"metisa-container-workload-{run_identifier}"
    workload_network_name = f"metisa-network-workload-{run_identifier}"
    backend_network_name = f"metisa-network-backend-{run_identifier}"
    egress_network_name = f"metisa-network-egress-{run_identifier}"
    host_output_path = _create_output_directory(host_run_directory, "output")
    host_logs_path = _create_logs_directory(host_run_directory, ".logs")
    host_scratch_path = _create_scratch_directory(host_run_directory, ".scratch")

    return SandboxContext(
        run_identifier=run_identifier,
        workload_container_name=workload_container_name,
        workload_network_name=workload_network_name,
        backend_network_name=backend_network_name,
        egress_network_name=egress_network_name,
        host_run_path=host_run_directory,
        host_output_path=host_output_path,
        host_logs_path=host_logs_path,
        host_scratch_path=host_scratch_path,
    )


def clean_up_run_directory(
    host_output_directory: Path,
    host_logs_directory: Path,
    host_scratch_directory: Path,
) -> None:
    """Clean up the run directory, preserving log files."""
    output_logs_dir = host_output_directory / ".logs"
    if output_logs_dir.exists():
        for source_path in output_logs_dir.rglob("*"):
            if not source_path.is_file():
                continue

            relative_path = source_path.relative_to(output_logs_dir)
            destination_path = host_logs_directory / relative_path
            destination_path.parent.mkdir(parents=True, exist_ok=True)

            if destination_path.exists():
                raise FileExistsError(
                    f"Log destination already exists: {destination_path}"
                )

            shutil.move(source_path, destination_path)

        shutil.rmtree(output_logs_dir)

    shutil.rmtree(host_scratch_directory)


def _create_run_identifier_and_directory() -> tuple[str, Path]:
    suffix = 0
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    run_identifier = f"run-{timestamp}"
    path: Path | None = None
    while not path and suffix <= 99:
        try:
            path = _create_run_directory(run_identifier)
        except FileExistsError:
            suffix += 1
            run_identifier = f"run-{timestamp}-{suffix:02d}"
    if not path:
        raise RuntimeError("Cannot create unique run identifier.")
    return run_identifier, path


def _create_run_directory(
    run_identifier: str,
) -> Path:
    run_directory = Path.cwd() / ".runs" / run_identifier
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_directory


def _create_output_directory(
    host_run_directory: Path,
    output_dir_name: str,
) -> Path:
    output_directory = host_run_directory / output_dir_name
    output_directory.mkdir(parents=True, exist_ok=False)
    return output_directory


def _create_logs_directory(
    host_run_directory: Path,
    logs_dir_name: str,
) -> Path:
    logs_directory = host_run_directory / logs_dir_name
    logs_directory.mkdir(parents=True, exist_ok=False)
    return logs_directory


def _create_scratch_directory(
    host_run_directory: Path,
    scratch_dir_name: str,
) -> Path:
    scratch_directory = host_run_directory / scratch_dir_name
    scratch_directory.mkdir(parents=True, exist_ok=False)
    return scratch_directory
