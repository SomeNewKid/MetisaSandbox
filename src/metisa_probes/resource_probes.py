"""Probes related to workload resource limits."""

from __future__ import annotations

from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult


def process_limit_is_configured(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the container process limit is configured."""
    probe_name = "resources__process_limit_is_configured"
    expected_process_limit = 64
    process_limit_paths = (
        Path("/sys/fs/cgroup/pids.max"),
        Path("/sys/fs/cgroup/pids/pids.max"),
    )

    process_limit_path = next(
        (path for path in process_limit_paths if path.exists()),
        None,
    )

    if process_limit_path is None:
        searched_paths = ", ".join(str(path) for path in process_limit_paths)
        message = f"Could not find a process limit at: {searched_paths}."
        return ProbeResult.failure(probe_name, message)

    try:
        raw_process_limit = process_limit_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        message = (
            f"Could not read {process_limit_path}: {type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    if raw_process_limit == "max":
        message = f"Process count is unlimited at {process_limit_path}."
        return ProbeResult.failure(probe_name, message)

    try:
        actual_process_limit = int(raw_process_limit)
    except ValueError:
        message = (
            f"Invalid process limit {raw_process_limit!r} at {process_limit_path}."
        )
        return ProbeResult.failure(probe_name, message)

    if actual_process_limit != expected_process_limit:
        message = (
            f"Expected process limit {expected_process_limit}, "
            f"got {actual_process_limit}."
        )
        return ProbeResult.failure(probe_name, message)

    message = f"Process count is limited to {actual_process_limit}."
    return ProbeResult.success(probe_name, message)


RESOURCE_PROBES = ProbeGroup(
    name="resources",
    probes=(process_limit_is_configured,),
)
