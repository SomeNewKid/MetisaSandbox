"""Command-line interface for the Metisa Runner module."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from metisa_common.specification_helper import get_workload_specification_path

_PROBES_MODULE = "metisa_probes"


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

    print("Docker probes starting...", end="\n", flush=True)
    os.environ["METISA_RUNTIME_ROLE"] = "probes"
    probes_exit_code = _run_probes_module(_PROBES_MODULE, specification_path)
    if probes_exit_code != 0:
        print("Sandbox probes failed.  Workload will not be run.", file=sys.stderr)
        return probes_exit_code

    print("Docker workload starting...", end="\n", flush=True)
    os.environ["METISA_RUNTIME_ROLE"] = "workload"

    try:
        _execute_workload(workload_module)
    except OSError as error:
        print(f"Failed to execute workload: {error}", file=sys.stderr)
        return 1


def _run_probes_module(
    module_name: str,
    specification_path: Path,
) -> int:
    result = subprocess.run(
        [sys.executable, "-m", module_name, str(specification_path)],
        check=False,
    )

    return result.returncode


def _execute_workload(
    module_name: str,
) -> NoReturn:
    arguments = [sys.executable, "-m", module_name]

    os.execv(sys.executable, arguments)
