"""Utility functions for container workspaces."""

from __future__ import annotations

import shutil
from fnmatch import fnmatchcase
from pathlib import Path

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


def clean_up_staged_source(
    staged_source_path: Path,
) -> None:
    """Clean up the staged source directory."""
    if staged_source_path.exists():
        shutil.rmtree(staged_source_path, ignore_errors=False)


def copy_directories_into_staged(
    source_directory: Path,
    target_directory: Path,
    child_directories: list[str],
) -> None:
    """Copy allowed directories and files into staged directory."""
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
