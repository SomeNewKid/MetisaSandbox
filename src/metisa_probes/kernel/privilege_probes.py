"""Probes related to process privilege acquisition."""

from __future__ import annotations

from pathlib import Path

from ..models import ProbeContext, ProbeGroup, ProbeResult


def no_new_privileges_is_enabled(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the process cannot acquire additional privileges."""
    probe_name = "kernel__privileges__no_new_privileges_is_enabled"
    process_status_path = Path("/proc/self/status")

    try:
        process_status = process_status_path.read_text(encoding="utf-8")
    except OSError as error:
        message = (
            f"Could not read {process_status_path}: {type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    for line in process_status.splitlines():
        field_name, separator, raw_value = line.partition(":")

        if separator == "" or field_name != "NoNewPrivs":
            continue

        value = raw_value.strip()
        if value == "1":
            return ProbeResult.success(
                probe_name,
                "No-new-privileges is enabled.",
            )

        return ProbeResult.failure(
            probe_name,
            f"Expected NoNewPrivs value 1, got {value!r}.",
        )

    return ProbeResult.failure(
        probe_name,
        f"NoNewPrivs field was not found in {process_status_path}.",
    )


PRIVILEGE_PROBES = ProbeGroup(
    name="privileges",
    probes=(no_new_privileges_is_enabled,),
)
