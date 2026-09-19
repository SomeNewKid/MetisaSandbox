"""Probes related to browser-debugging endpoints."""

from __future__ import annotations

import os
from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult

_DEBUGGING_ARGUMENTS = (
    "--remote-debugging-port",
    "--remote-debugging-address",
    "--remote-debugging-pipe",
    "--start-debugger-server",
    "--marionette",
)

_DEBUGGING_ENVIRONMENT_VARIABLES = (
    "BROWSER_WS_ENDPOINT",
    "CDP_ENDPOINT",
    "CDP_URL",
    "PLAYWRIGHT_CDP_URL",
)


def debugging_command_line_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify no process has browser-debugging command-line arguments."""
    probe_name = "browser__debugging_command_line_is_absent"
    proc_path = Path("/proc")
    configured_processes: list[str] = []

    try:
        process_paths = sorted(
            (path for path in proc_path.iterdir() if path.name.isdigit()),
            key=lambda path: int(path.name),
        )
    except OSError as error:
        message = f"Could not enumerate {proc_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    for process_path in process_paths:
        command_line_path = process_path / "cmdline"

        try:
            command_line_bytes = command_line_path.read_bytes()
        except FileNotFoundError:
            continue
        except OSError as error:
            message = (
                f"Could not read {command_line_path}: {type(error).__name__}: {error}"
            )
            return ProbeResult.failure(probe_name, message)

        command_line = command_line_bytes.replace(b"\0", b" ").decode(
            "utf-8",
            errors="replace",
        )

        matching_arguments = sorted(
            argument for argument in _DEBUGGING_ARGUMENTS if argument in command_line
        )

        if matching_arguments:
            arguments = ", ".join(matching_arguments)
            configured_processes.append(f"PID {process_path.name}: {arguments}")

    if configured_processes:
        processes = "; ".join(configured_processes)
        message = f"Browser-debugging arguments found: {processes}."
        return ProbeResult.failure(probe_name, message)

    message = "No browser-debugging command-line arguments were found."
    return ProbeResult.success(probe_name, message)


def debugging_environment_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify no browser-debugging endpoint is configured by environment."""
    probe_name = "browser__debugging_environment_is_absent"
    configured_variables = {
        variable_name: os.environ[variable_name]
        for variable_name in _DEBUGGING_ENVIRONMENT_VARIABLES
        if variable_name in os.environ
    }

    if configured_variables:
        variables = ", ".join(
            f"{name}={value!r}" for name, value in sorted(configured_variables.items())
        )
        message = f"Browser-debugging environment variables found: {variables}."
        return ProbeResult.failure(probe_name, message)

    message = "No browser-debugging environment variables were found."
    return ProbeResult.success(probe_name, message)


BROWSER_PROBES = ProbeGroup(
    name="browser",
    probes=(
        debugging_command_line_is_absent,
        debugging_environment_is_absent,
    ),
)
