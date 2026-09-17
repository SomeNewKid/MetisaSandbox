"""Command-line interface for the Metisa Probes module."""

from __future__ import annotations

import json
from pathlib import Path

from .docker_probes import DOCKER_PROBES
from .filesystem_probes import FILESYSTEM_PROBES
from .identity_probes import IDENTITY_PROBES
from .models import ProbeContext, ProbeGroup, ProbeResult
from .network_probes import NETWORK_PROBES


def main() -> int:
    """Run the Metisa probes."""
    success = True
    probe_context = ProbeContext()
    log_path = _get_log_path(probe_context)

    probe_groups = (
        DOCKER_PROBES,
        FILESYSTEM_PROBES,
        IDENTITY_PROBES,
        NETWORK_PROBES,
    )

    for probe_group in probe_groups:
        group_passed = _run_probe_group(probe_group, probe_context, log_path)

        if not group_passed:
            success = False

    return 0 if success else 1


def _run_probe_group(
    probe_group: ProbeGroup, 
    probe_context: ProbeContext, 
    log_path: Path
) -> bool:
    success = True

    for probe in probe_group.probes:
        result = probe(probe_context)
        _write_probe_log_entry(log_path, result)
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.name}: {result.message}")

        if not result.passed:
            success = False

    return success


def _get_log_path(probe_context: ProbeContext) -> Path:
    output_volume = Path(probe_context.output_volume)
    log_directory = output_volume / ".logs"
    log_directory.mkdir(parents=True, exist_ok=True)

    return log_directory / "metisa_probes.jsonl"


def _write_probe_log_entry(log_path: Path, probe_result: ProbeResult) -> None:
    log_entry = {
        "name": probe_result.name,
        "passed": probe_result.passed,
        "message": probe_result.message,
    }
    with log_path.open("a", encoding="utf-8") as log_file:
        json.dump(log_entry, log_file)
        log_file.write("\n")