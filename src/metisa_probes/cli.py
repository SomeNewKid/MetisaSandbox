"""Command-line interface for the Metisa Probes module."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from metisa_common.specification_helper import load_specification

from .container.browser_probes import BROWSER_PROBES
from .container.docker_probes import DOCKER_PROBES
from .container.environment_probes import ENVIRONMENT_PROBES
from .container.filesystem_probes import FILESYSTEM_PROBES
from .container.identity_probes import IDENTITY_PROBES
from .container.network_probes import NETWORK_PROBES
from .container.system_command_probes import SYSTEM_COMMAND_PROBES
from .container.system_package_probes import SYSTEM_PACKAGE_PROBES
from .kernel.landlock_probes import LANDLOCK_PROBES
from .kernel.linux_capability_probes import LINUX_CAPABILITY_PROBES
from .kernel.network_probes import KERNEL_NETWORK_PROBES
from .kernel.privilege_probes import PRIVILEGE_PROBES
from .kernel.resource_probes import RESOURCE_PROBES
from .models import ProbeContext, ProbeGroup, ProbeResult
from .python.diagnostic_probes import DIAGNOSTIC_PROBES
from .python.hardware_probes import HARDWARE_PROBES
from .python.process_probes import PROCESS_PROBES
from .python.python_probes import PYTHON_PROBES
from .python.socket_probes import SOCKET_PROBES


def main(
    argv: list[str] | None = None,
) -> int:
    """Run the Metisa probes."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("Error: no metisa.toml argument.", file=sys.stderr)
        return 1

    specification_arg = args[0]
    if not specification_arg:
        print("Error: invalid metisa.toml argument.", file=sys.stderr)
        return 1

    specification_path = Path(specification_arg)
    if not specification_path.is_file():
        print("Error: invalid metisa.toml argument.", file=sys.stderr)
        return 1

    specification = load_specification(specification_path)

    success = True
    probe_context = ProbeContext(specification)
    log_path = _get_log_path(probe_context)

    probe_groups = (
        BROWSER_PROBES,
        DOCKER_PROBES,
        ENVIRONMENT_PROBES,
        FILESYSTEM_PROBES,
        IDENTITY_PROBES,
        NETWORK_PROBES,
        SYSTEM_COMMAND_PROBES,
        SYSTEM_PACKAGE_PROBES,
        LANDLOCK_PROBES,
        LINUX_CAPABILITY_PROBES,
        KERNEL_NETWORK_PROBES,
        PRIVILEGE_PROBES,
        RESOURCE_PROBES,
        DIAGNOSTIC_PROBES,
        HARDWARE_PROBES,
        PYTHON_PROBES,
        PROCESS_PROBES,
        SOCKET_PROBES,
    )

    for probe_group in probe_groups:
        group_passed = _run_probe_group(probe_group, probe_context, log_path)

        if not group_passed:
            success = False

    return 0 if success else 1


def _run_probe_group(
    probe_group: ProbeGroup,
    probe_context: ProbeContext,
    log_path: Path,
) -> bool:
    success = True

    for probe in probe_group.probes:
        try:
            result = probe(probe_context)
        except Exception as error:
            probe_name = f"{probe_group.name}__{probe.__name__}"
            message = (
                f"Probe raised an unexpected exception: {type(error).__name__}: {error}"
            )
            result = ProbeResult.failure(probe_name, message)

        _write_probe_log_entry(log_path, result)
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.name}: {result.message}")

        if not result.passed:
            success = False

    return success


def _get_log_path(
    probe_context: ProbeContext,
) -> Path:
    output_volume = Path(probe_context.output_volume)
    log_directory = output_volume / ".logs"
    log_directory.mkdir(parents=True, exist_ok=True)

    return log_directory / "metisa_probes.jsonl"


def _write_probe_log_entry(
    log_path: Path,
    probe_result: ProbeResult,
) -> None:
    log_entry = {
        "name": probe_result.name,
        "passed": probe_result.passed,
        "message": probe_result.message,
    }
    with log_path.open("a", encoding="utf-8") as log_file:
        json.dump(log_entry, log_file)
        log_file.write("\n")
