"""Command-line interface for the Metisa Runner module."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_PROBES_MODULE = "metisa_probes"
_SANDBOX_OUTPUT_DIR_ENV = "SANDBOX_OUTPUT_DIR"


def main(argv: list[str] | None = None) -> int:
    """Run the Metisa probes module and then the workload module."""

    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("Error: no workload module argument.", file=sys.stderr)
        return 1

    workload_module = args[0]

    print("Docker probes starting...", end="\n", flush=True)
    probes_exit_code = _run_python_module(_PROBES_MODULE)
    if probes_exit_code != 0:
        print("Sandbox probes failed.  Workload will not be run.", file=sys.stderr)
        return probes_exit_code

    print("Docker workload starting...", end="\n", flush=True)
    workload_exit_code = _run_workload_module(workload_module)

    return workload_exit_code


def _run_python_module(module_name: str) -> int:
    result = subprocess.run(
        [sys.executable, "-m", module_name],
        check=False,
    )

    return result.returncode


def _run_workload_module(module_name: str) -> int:
    log_path = _get_workload_log_path()

    process = subprocess.Popen(
        [sys.executable, "-m", module_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=0,
    )

    with log_path.open("a", encoding="utf-8") as log_file:
        if process.stdout is not None:
            while True:
                chunk = process.stdout.read(1)
                if chunk == "":
                    break

                print(chunk, end="", flush=True)
                log_file.write(chunk)
                log_file.flush()

    return process.wait()


def _get_workload_log_path() -> Path:
    output_dir = os.environ.get(_SANDBOX_OUTPUT_DIR_ENV)
    if not output_dir:
        raise RuntimeError(f"{_SANDBOX_OUTPUT_DIR_ENV} is not set.")

    log_dir = Path(output_dir) / ".logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    return log_dir / "workload.txt"