"""Probes for the kernel-enforced Landlock policy."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

from ..models import ProbeContext, ProbeGroup, ProbeResult

_DENIED_DIRECTORY = Path("/metisa-denied")
_DENIED_FILE = _DENIED_DIRECTORY / "readable.txt"


def unlisted_file_read_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Landlock denies reading a file outside its allowlist."""
    del probe_context

    probe_name = "kernel__landlock__unlisted_file_read_is_denied"

    try:
        file_status = _DENIED_FILE.stat()
    except OSError as error:
        message = f"Could not inspect Landlock canary {_DENIED_FILE}: {error}"
        return ProbeResult.failure(probe_name, message)

    if not stat.S_ISREG(file_status.st_mode):
        message = f"Landlock canary is not a regular file: {_DENIED_FILE}."
        return ProbeResult.failure(probe_name, message)

    if not file_status.st_mode & stat.S_IROTH:
        message = f"Landlock canary is not world-readable: {_DENIED_FILE}."
        return ProbeResult.failure(probe_name, message)

    try:
        file_descriptor = os.open(_DENIED_FILE, os.O_RDONLY)
    except PermissionError as error:
        if error.errno == errno.EACCES:
            message = f"Landlock denied reading {_DENIED_FILE}."
            return ProbeResult.success(probe_name, message)

        message = f"Reading {_DENIED_FILE} failed unexpectedly: {error}."
        return ProbeResult.failure(probe_name, message)
    except OSError as error:
        message = f"Reading {_DENIED_FILE} failed unexpectedly: {error}."
        return ProbeResult.failure(probe_name, message)

    os.close(file_descriptor)

    message = f"Landlock allowed reading unlisted file {_DENIED_FILE}."
    return ProbeResult.failure(probe_name, message)


def unlisted_directory_enumeration_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Landlock denies listing a directory outside its allowlist."""
    del probe_context

    probe_name = "kernel__landlock__unlisted_directory_enumeration_is_denied"

    try:
        directory_status = _DENIED_DIRECTORY.stat()
    except OSError as error:
        message = (
            f"Could not inspect Landlock canary directory {_DENIED_DIRECTORY}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    if not stat.S_ISDIR(directory_status.st_mode):
        message = f"Landlock canary is not a directory: {_DENIED_DIRECTORY}."
        return ProbeResult.failure(probe_name, message)

    try:
        with os.scandir(_DENIED_DIRECTORY) as entries:
            list(entries)
    except PermissionError as error:
        if error.errno == errno.EACCES:
            message = f"Landlock denied enumeration of {_DENIED_DIRECTORY}."
            return ProbeResult.success(probe_name, message)

        message = f"Enumerating {_DENIED_DIRECTORY} failed unexpectedly: {error}."
        return ProbeResult.failure(probe_name, message)
    except OSError as error:
        message = f"Enumerating {_DENIED_DIRECTORY} failed unexpectedly: {error}."
        return ProbeResult.failure(probe_name, message)

    message = f"Landlock allowed enumeration of unlisted directory {_DENIED_DIRECTORY}."
    return ProbeResult.failure(probe_name, message)


LANDLOCK_PROBES = ProbeGroup(
    name="landlock",
    probes=(
        unlisted_file_read_is_denied,
        unlisted_directory_enumeration_is_denied,
    ),
)
