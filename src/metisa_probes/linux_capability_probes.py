"""Probes related to Linux process capabilities."""

from __future__ import annotations

from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult

_CAPABILITY_FIELDS = (
    "CapInh",
    "CapPrm",
    "CapEff",
    "CapBnd",
    "CapAmb",
)


def capability_sets_are_empty(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify all Linux capability sets are empty."""
    probe_name = "linux_capabilities__capability_sets_are_empty"
    process_status_path = Path("/proc/self/status")

    try:
        process_status = process_status_path.read_text(encoding="utf-8")
    except OSError as error:
        message = (
            f"Could not read {process_status_path}: {type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    capability_values: dict[str, int] = {}

    for line in process_status.splitlines():
        field_name, separator, raw_value = line.partition(":")
        if separator == "" or field_name not in _CAPABILITY_FIELDS:
            continue

        try:
            capability_values[field_name] = int(raw_value.strip(), 16)
        except ValueError:
            message = (
                f"Capability field {field_name} has invalid hexadecimal value "
                f"{raw_value.strip()!r}."
            )
            return ProbeResult.failure(probe_name, message)

    missing_fields = sorted(set(_CAPABILITY_FIELDS) - capability_values.keys())
    if missing_fields:
        fields = ", ".join(missing_fields)
        message = f"Capability fields missing from {process_status_path}: {fields}."
        return ProbeResult.failure(probe_name, message)

    nonempty_fields = {
        field_name: value
        for field_name, value in capability_values.items()
        if value != 0
    }

    if nonempty_fields:
        fields = ", ".join(
            f"{field_name}=0x{value:016x}"
            for field_name, value in sorted(nonempty_fields.items())
        )
        message = f"Nonempty Linux capability sets found: {fields}."
        return ProbeResult.failure(probe_name, message)

    message = "All Linux capability sets are empty."
    return ProbeResult.success(probe_name, message)


LINUX_CAPABILITY_PROBES = ProbeGroup(
    name="linux_capabilities",
    probes=(capability_sets_are_empty,),
)
