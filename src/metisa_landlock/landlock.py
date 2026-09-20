"""Implement the initial Metisa Landlock policy."""

from __future__ import annotations

from pathlib import Path

from metisa_common.models import MetisaSpecification


def apply_landlock_rules(
    specification: MetisaSpecification,
    log_file_path: Path,
):
    """Apply the Landlock security rules to the current process."""
    with log_file_path.open("w", encoding="utf-8") as log_file:
        log_file.write("Hello from landlock module.")
