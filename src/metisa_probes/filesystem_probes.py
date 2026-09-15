"""Probes of the file system."""

from __future__ import annotations

from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult


def sandbox_output_volume_is_writable(probe_context: ProbeContext) -> ProbeResult:
    """Verify the configured output volume is writable."""
    probe_name = "filesystem__sandbox_output_volume_is_writable"
    output_volume = Path(probe_context.output_volume)
    probe_file = output_volume / ".probe-write-test"

    try:
        probe_file.write_text(probe_name)
        if not probe_file.exists():
            return ProbeResult.failure(probe_name, f"File not created at {probe_file}.")
        probe_file.unlink()
    except OSError as error:
        return ProbeResult.failure(probe_name, str(error))

    return ProbeResult.success(probe_name, f"File created at {probe_file}")


def sandbox_source_volume_is_not_writable(probe_context: ProbeContext) -> ProbeResult:
    """Verify the configured source volume is not writable."""
    probe_name = "filesystem__sandbox_source_volume_is_not_writable"
    source_volume = Path(probe_context.source_volume)
    probe_file = source_volume / ".probe-write-test"

    try:
        probe_file.write_text(probe_name)
        if probe_file.exists():
            probe_file.unlink()
            return ProbeResult.failure(probe_name, f"File created at {probe_file}")
    except OSError as error:
        return ProbeResult.success(probe_name, str(error))

    return ProbeResult.success(probe_name, f"File not created at {probe_file}")


def sandbox_source_module_is_not_writable(probe_context: ProbeContext) -> ProbeResult:
    """Verify the configured source module is not writable."""
    probe_name = "filesystem__sandbox_source_module_is_not_writable"
    source_volume = Path(probe_context.source_volume)
    probe_file = source_volume / "metisa_probes" / ".probe-write-test"

    try:
        probe_file.write_text(probe_name)
        if probe_file.exists():
            probe_file.unlink()
            return ProbeResult.failure(probe_name, f"File created at {probe_file}")
    except OSError as error:
        return ProbeResult.success(probe_name, str(error))

    return ProbeResult.success(probe_name, f"File not created at {probe_file}")


FILESYSTEM_PROBES = ProbeGroup(
    name="filesystem",
    probes=(
        sandbox_output_volume_is_writable,
        # sandbox_source_volume_is_not_writable, # disabled until later hardening
        sandbox_source_module_is_not_writable,
    ),
)
