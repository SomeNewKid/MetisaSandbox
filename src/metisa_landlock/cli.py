"""Command-line interface for the Metisa Landlock module."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NoReturn

from metisa_common.specification_helper import (
    get_workload_specification_path,
    load_specification,
)

from .landlock import apply_landlock_rules

_RUNNER_MODULE = "metisa_runner"
_SANDBOX_OUTPUT_DIR_ENV = "SANDBOX_OUTPUT_DIR"


def main(
    argv: list[str] | None = None,
) -> int:
    """Run the Metisa probes module and then the workload module."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("Error: no workload module argument.", file=sys.stderr)
        return 1

    workload_module = args[0]
    specification_path = get_workload_specification_path(workload_module)
    specification = load_specification(specification_path)
    log_file_path = _get_landlock_log_path()

    print("Metisa landlock starting...", end="\n", flush=True)
    try:
        apply_landlock_rules(specification, log_file_path)
    except Exception as error:
        print(f"Failed to apply Landlock rules: {error}", file=sys.stderr)
        return 1

    try:
        return _execute_runner(workload_module)
    except OSError as error:
        print(f"Failed to execute runner: {error}", file=sys.stderr)
        return 1


def _execute_runner(workload_module: str) -> NoReturn:
    arguments = [
        sys.executable,
        "-I",  # Run the Python interpreter in isolated mode
        "-B",  # Don't write .pyc files on import
        "-m",
        _RUNNER_MODULE,
        workload_module,
    ]
    os.environ["METISA_RUNTIME_ROLE"] = "runner"

    os.execv(sys.executable, arguments)


def _get_landlock_log_path() -> Path:
    output_dir = os.environ.get(_SANDBOX_OUTPUT_DIR_ENV)
    if not output_dir:
        raise RuntimeError(f"{_SANDBOX_OUTPUT_DIR_ENV} is not set.")

    log_dir = Path(output_dir) / ".logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    return log_dir / "landlock.txt"
