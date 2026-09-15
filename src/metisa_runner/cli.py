"""Command-line interface for the Metisa Runner module."""

from __future__ import annotations

import subprocess
import sys

_PROBES_MODULE = "metisa_probes"


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
    workload_exit_code = _run_python_module(workload_module)

    return workload_exit_code


def _run_python_module(module_name: str) -> int:
    result = subprocess.run(
        [sys.executable, "-m", module_name],
        check=False,
    )

    return result.returncode
