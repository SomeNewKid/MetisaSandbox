"""Probes related to system package management."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult


def apt_entry_point_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the apt entry point is unavailable."""
    return _entry_point_is_absent("apt")


def apt_get_entry_point_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the apt-get entry point is unavailable."""
    return _entry_point_is_absent("apt-get")


def dpkg_entry_point_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the dpkg entry point is unavailable."""
    return _entry_point_is_absent("dpkg")


def dpkg_query_entry_point_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the dpkg-query entry point is unavailable."""
    return _entry_point_is_absent("dpkg-query")


def apt_state_directory_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the APT state directory is absent."""
    return _path_is_absent(Path("/var/lib/apt"), "apt_state_directory")


def apt_cache_directory_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the APT cache directory is absent."""
    return _path_is_absent(Path("/var/cache/apt"), "apt_cache_directory")


def dpkg_state_directory_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the dpkg state directory is absent."""
    return _path_is_absent(Path("/var/lib/dpkg"), "dpkg_state_directory")


def apt_log_directory_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the APT log directory is absent."""
    return _path_is_absent(Path("/var/log/apt"), "apt_log_directory")


SYSTEM_PACKAGE_PROBES = ProbeGroup(
    name="system_packages",
    probes=(
        apt_entry_point_is_absent,
        apt_get_entry_point_is_absent,
        dpkg_entry_point_is_absent,
        dpkg_query_entry_point_is_absent,
        apt_state_directory_is_absent,
        apt_cache_directory_is_absent,
        dpkg_state_directory_is_absent,
        apt_log_directory_is_absent,
    ),
)


def _entry_point_is_absent(entry_point_name: str) -> ProbeResult:
    normalized_name = entry_point_name.replace("-", "_")
    probe_name = f"system_packages__{normalized_name}_entry_point_is_absent"
    entry_point_paths: set[Path] = set()

    discovered_entry_point = shutil.which(entry_point_name)
    if discovered_entry_point is not None:
        entry_point_paths.add(Path(discovered_entry_point))

    executable_directories = (
        Path("/bin"),
        Path("/sbin"),
        Path("/usr/bin"),
        Path("/usr/sbin"),
        Path("/usr/local/bin"),
        Path("/usr/local/sbin"),
    )

    for executable_directory in executable_directories:
        entry_point_path = executable_directory / entry_point_name
        if os.path.lexists(entry_point_path):
            entry_point_paths.add(entry_point_path)

    if entry_point_paths:
        paths = ", ".join(str(path) for path in sorted(entry_point_paths))
        message = f"Entry point {entry_point_name} found at: {paths}."
        return ProbeResult.failure(probe_name, message)

    message = f"Entry point {entry_point_name} is unavailable."
    return ProbeResult.success(probe_name, message)


def _path_is_absent(path: Path, path_name: str) -> ProbeResult:
    probe_name = f"system_packages__{path_name}_is_absent"

    if os.path.lexists(path):
        message = f"System package-management path exists at {path}."
        return ProbeResult.failure(probe_name, message)

    message = f"System package-management path is absent at {path}."
    return ProbeResult.success(probe_name, message)
