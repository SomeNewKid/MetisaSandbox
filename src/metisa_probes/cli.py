"""Command-line interface for the Metisa Probes module."""

from __future__ import annotations

from .docker_probes import DOCKER_PROBES
from .filesystem_probes import FILESYSTEM_PROBES
from .models import ProbeContext, ProbeGroup


def main() -> int:
    """Run the Metisa probes."""
    success = True
    probe_context = ProbeContext()

    probe_groups = (
        DOCKER_PROBES,
        FILESYSTEM_PROBES,
    )

    for probe_group in probe_groups:
        group_passed = _run_probe_group(probe_group, probe_context)

        if not group_passed:
            success = False

    return 0 if success else 1


def _run_probe_group(probe_group: ProbeGroup, probe_context: ProbeContext) -> bool:
    success = True

    for probe in probe_group.probes:
        result = probe(probe_context)
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.name}: {result.message}")

        if not result.passed:
            success = False

    return success

