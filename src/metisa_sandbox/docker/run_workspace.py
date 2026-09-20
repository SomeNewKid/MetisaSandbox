"""Manages the host filesystem state for a run."""

from __future__ import annotations

import shutil
from datetime import datetime
from fnmatch import fnmatchcase
from pathlib import Path

from .models import SandboxContext

_IGNORED_DIRECTORY_PATTERNS = (
    ".*",
    "__pycache__",
    "*.egg-info",
    "*.dist-info",
    "script",
    "scripts",
    "tests",
)

_IGNORED_FILE_PATTERNS = (
    ".*",
    "*.pyc",
    "*.pyo",
    "pyproject.toml",
    "requirements*.txt",
    "setup.cfg",
    "setup.py",
    "tox.ini",
)


def create_sandbox_context(
    image_identifier: str,
) -> SandboxContext:
    """Create a sandbox context for the given Docker image and tag."""
    run_identifier = _create_run_identifier()
    network_name = f"sandbox-{run_identifier}"
    host_source_path = Path.cwd() / "src"
    host_run_directory = _create_run_directory(run_identifier)
    output_dir_name = "output"
    host_output_path = _create_output_directory(host_run_directory, output_dir_name)

    return SandboxContext(
        image_reference=image_identifier,
        run_identifier=run_identifier,
        network_name=network_name,
        host_run_path=host_run_directory,
        host_source_path=host_source_path,
        host_output_path=host_output_path,
    )


def create_staged_source_directory(
    sandbox_context: SandboxContext,
    workload_module: str,
) -> Path:
    """Create a staged source directory for the sandbox context."""
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


def create_log_file(
    sandbox_context: SandboxContext,
) -> Path:
    """Create a log file for the sandbox context."""
    logs_dir = sandbox_context.host_run_path / ".logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "docker.txt"

    with log_file.open("w", encoding="utf-8") as file:
        file.write("Running Docker container\n")

        file.write("Image: ")
        file.write(sandbox_context.image_reference)
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


def clean_up_staged_source(
    staged_source_path: Path,
) -> None:
    """Clean up the staged source directory."""
    if staged_source_path.exists():
        shutil.rmtree(staged_source_path, ignore_errors=False)


def _copy_directories_into_staged(
    source_directory: Path,
    target_directory: Path,
    child_directories: list[str],
) -> None:
    for child_directory in child_directories:
        from_dir = source_directory / child_directory
        to_dir = target_directory / child_directory
        shutil.copytree(src=from_dir, dst=to_dir, ignore=_get_ignored_source_entries)


def _get_ignored_source_entries(
    directory: str,
    entry_names: list[str],
) -> set[str]:
    ignored_entries: set[str] = set()
    directory_path = Path(directory)

    for entry_name in entry_names:
        entry_path = directory_path / entry_name

        if entry_path.is_symlink():
            ignored_entries.add(entry_name)
            continue

        if entry_path.is_dir():
            patterns = _IGNORED_DIRECTORY_PATTERNS
        else:
            patterns = _IGNORED_FILE_PATTERNS

        if any(fnmatchcase(entry_name, pattern) for pattern in patterns):
            ignored_entries.add(entry_name)

    return ignored_entries


def _create_run_identifier() -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return f"run-{timestamp}"


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
