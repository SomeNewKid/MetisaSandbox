"""Manages the host filesystem state for the Metisa container."""

from __future__ import annotations

import shutil
from fnmatch import fnmatchcase
from pathlib import Path

from ..sandbox_context import SandboxContext

LANDLOCK_MODULE_NAME = "metisa_landlock"

_COMMON_MODULE_NAME = "metisa_common"
_RUNNER_MODULE_NAME = "metisa_runner"
_PROBES_MODULE_NAME = "metisa_probes"

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


def create_staged_source_directory(
    sandbox_context: SandboxContext,
    workload_module: str,
) -> Path:
    """Create a staged source directory for the sandbox context."""
    local_source_path = Path.cwd() / "src"
    staged_source_path = sandbox_context.host_run_path / "source"
    staged_source_path.mkdir(parents=True, exist_ok=False)

    _copy_directories_into_staged(
        local_source_path,
        staged_source_path,
        [
            LANDLOCK_MODULE_NAME,
            _COMMON_MODULE_NAME,
            _RUNNER_MODULE_NAME,
            _PROBES_MODULE_NAME,
            workload_module,
        ],
    )

    return staged_source_path


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
