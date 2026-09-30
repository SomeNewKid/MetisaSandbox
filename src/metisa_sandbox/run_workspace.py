"""Manages the host filesystem state for a run."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .sandbox_context import SandboxContext


def create_sandbox_context() -> SandboxContext:
    """Create a sandbox context."""
    run_identifier, host_run_directory = _create_run_identifier_and_directory()
    private_network_name = f"metisa-private-{run_identifier}"
    egress_network_name = f"metisa-egress-{run_identifier}"
    output_dir_name = "output"
    host_output_path = _create_output_directory(host_run_directory, output_dir_name)

    return SandboxContext(
        run_identifier=run_identifier,
        private_network_name=private_network_name,
        egress_network_name=egress_network_name,
        host_run_path=host_run_directory,
        host_output_path=host_output_path,
    )


def create_log_file(
    sandbox_context: SandboxContext,
    image_reference: str,
) -> Path:
    """Create a log file for the sandbox context."""
    logs_dir = sandbox_context.host_run_path / ".logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    metisa_logs_dir = logs_dir / "metisa"
    metisa_logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = metisa_logs_dir / "docker.txt"

    with log_file.open("w", encoding="utf-8") as file:
        file.write("Running Docker container\n")

        file.write("Image: ")
        file.write(image_reference)
        file.write("\n")

    return log_file


def append_log_file(
    log_file: Path,
    messages: list[str],
) -> None:
    """Append messages to the specified log file."""
    with log_file.open("a", encoding="utf-8") as file:
        for message in messages:
            file.write(message)
            file.write("\n")


def clean_up_run_directory(
    host_run_directory: Path,
    output_directory: Path,
) -> None:
    """Clean up the run directory, preserving log files."""
    output_logs_dir = output_directory / ".logs"
    if output_logs_dir.exists():
        run_logs_dir = host_run_directory / ".logs"
        run_logs_dir.mkdir(parents=True, exist_ok=True)
        for item in output_logs_dir.iterdir():
            shutil.move(item, run_logs_dir)
        output_logs_dir.rmdir()


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
