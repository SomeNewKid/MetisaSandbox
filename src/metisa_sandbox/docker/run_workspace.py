"""
Manages the host filesystem state for a run
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .docker_image import create_image_reference
from .models import SandboxContext


def create_sandbox_context(image_name: str, image_tag: str) -> SandboxContext:
    run_identifier = _create_run_identifier()
    network_name = f"sandbox-{run_identifier}"
    host_source_path = Path.cwd() / "src"
    host_run_directory = _create_run_directory(run_identifier)
    output_dir_name = "output"
    host_output_path = _create_output_directory(host_run_directory, output_dir_name)

    return SandboxContext(
        image_name=image_name,
        image_tag=image_tag,
        identifier=run_identifier,
        network_name=network_name,
        host_run_path=host_run_directory,
        host_source_path=host_source_path,
        host_output_path=host_output_path,
    )


def create_staged_source_directory(
    sandbox_context: SandboxContext, workload_module: str
) -> Path:
    staged_source_path = sandbox_context.host_run_path / "source"
    staged_source_path.mkdir(parents=True, exist_ok=False)

    _copy_directories_into_staged(
        sandbox_context.host_source_path,
        staged_source_path,
        [
            sandbox_context.common_module_name,
            sandbox_context.runner_module_name,
            sandbox_context.probes_module_name,
            workload_module,
        ],
    )

    return staged_source_path


def create_log_file(sandbox_context: SandboxContext) -> Path:
    logs_dir = sandbox_context.host_run_path / ".logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "docker.txt"

    image_reference = _create_image_reference(sandbox_context)

    with log_file.open("w", encoding="utf-8") as file:
        file.write("Running Docker container\n")

        file.write("Image: ")
        file.write(image_reference)
        file.write("\n")

    return log_file


def append_log_file(log_file: Path, messages: list[str]) -> None:
    with log_file.open("a", encoding="utf-8") as file:
        for message in messages:
            file.write(message)
            file.write("\n")


def clean_up_run_directory(
    host_run_directory: Path,
    output_directory: Path,
    staged_source_path: Path | None,
) -> None:
    output_logs_dir = output_directory / ".logs"
    if output_logs_dir.exists():
        run_logs_dir = host_run_directory / ".logs"
        run_logs_dir.mkdir(parents=True, exist_ok=True)
        for item in output_logs_dir.iterdir():
            shutil.move(item, run_logs_dir)
        output_logs_dir.rmdir()

    if staged_source_path is not None and staged_source_path.exists():
        shutil.rmtree(staged_source_path, ignore_errors=False)


def _copy_directories_into_staged(
    source_directory: Path, target_directory: Path, child_directories: list[str]
) -> None:
    for child_directory in child_directories:
        from_dir = source_directory / child_directory
        to_dir = target_directory / child_directory
        shutil.copytree(from_dir, to_dir)


def _create_run_identifier() -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return f"run-{timestamp}"


def _create_run_directory(run_identifier: str) -> Path:
    run_directory = Path.cwd() / ".runs" / run_identifier
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_directory


def _create_output_directory(host_run_directory: Path, output_dir_name: str) -> Path:
    output_directory = host_run_directory / output_dir_name
    output_directory.mkdir(parents=True, exist_ok=False)
    return output_directory


def _create_image_reference(sandbox_context: SandboxContext) -> str:
    return create_image_reference(sandbox_context.image_name, sandbox_context.image_tag)
