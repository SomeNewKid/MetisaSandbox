"""Command-line interface for the Metisa Probes module."""

from __future__ import annotations

from .filesystem_probes import FILESYSTEM_PROBES
from .models import ProbeContext


def main() -> int:
    """Run the Metisa probes."""
    success = True
    probe_context = ProbeContext()

    for probe in FILESYSTEM_PROBES.probes:
        result = probe(probe_context)
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.name}: {result.message}")

        if not result.passed:
            success = False

    return 0 if success else 1
