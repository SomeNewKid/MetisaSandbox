"""Probes related to workload resource limits."""

from __future__ import annotations

from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult

_EXPECTED_MEMORY_LIMIT_BYTES = 128 * 1024 * 1024


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


def memory_limit_is_configured(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the container memory limit is 128 MiB."""
    probe_name = "resources__memory_limit_is_configured"
    memory_limit_paths = (
        Path("/sys/fs/cgroup/memory.max"),
        Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    )
    memory_limit_path = next(
        (path for path in memory_limit_paths if path.exists()),
        None,
    )

    if memory_limit_path is None:
        searched_paths = ", ".join(str(path) for path in memory_limit_paths)
        message = f"Could not find a memory limit at: {searched_paths}."
        return ProbeResult.failure(probe_name, message)

    actual_memory_limit, error_result = _read_cgroup_integer(
        probe_name=probe_name,
        cgroup_path=memory_limit_path,
        resource_name="memory limit",
    )

    if error_result is not None:
        return error_result

    if actual_memory_limit != _EXPECTED_MEMORY_LIMIT_BYTES:
        message = (
            f"Expected memory limit {_EXPECTED_MEMORY_LIMIT_BYTES} bytes, "
            f"got {actual_memory_limit} bytes."
        )
        return ProbeResult.failure(probe_name, message)

    message = f"Memory is limited to {actual_memory_limit} bytes."
    return ProbeResult.success(probe_name, message)


def additional_swap_is_disabled(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the container has no swap allowance beyond its memory limit."""
    probe_name = "resources__additional_swap_is_disabled"
    cgroup_v2_swap_path = Path("/sys/fs/cgroup/memory.swap.max")

    if cgroup_v2_swap_path.exists():
        actual_swap_limit, error_result = _read_cgroup_integer(
            probe_name=probe_name,
            cgroup_path=cgroup_v2_swap_path,
            resource_name="additional swap limit",
        )

        if error_result is not None:
            return error_result

        if actual_swap_limit != 0:
            message = (
                f"Expected no additional swap allowance, got {actual_swap_limit} bytes."
            )
            return ProbeResult.failure(probe_name, message)

        message = "Additional swap allowance is disabled."
        return ProbeResult.success(probe_name, message)

    cgroup_v1_memory_path = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    cgroup_v1_memory_swap_path = Path(
        "/sys/fs/cgroup/memory/memory.memsw.limit_in_bytes"
    )

    if not cgroup_v1_memory_path.exists() or not cgroup_v1_memory_swap_path.exists():
        message = (
            "Could not find cgroup v2 swap limit or cgroup v1 memory and swap limits."
        )
        return ProbeResult.failure(probe_name, message)

    actual_memory_limit, memory_error = _read_cgroup_integer(
        probe_name=probe_name,
        cgroup_path=cgroup_v1_memory_path,
        resource_name="memory limit",
    )

    if memory_error is not None:
        return memory_error

    actual_memory_swap_limit, memory_swap_error = _read_cgroup_integer(
        probe_name=probe_name,
        cgroup_path=cgroup_v1_memory_swap_path,
        resource_name="combined memory and swap limit",
    )

    if memory_swap_error is not None:
        return memory_swap_error

    if actual_memory_swap_limit != actual_memory_limit:
        message = (
            f"Memory limit is {actual_memory_limit} bytes, but combined memory "
            f"and swap limit is {actual_memory_swap_limit} bytes."
        )
        return ProbeResult.failure(probe_name, message)

    message = "Combined memory and swap limit equals the memory limit."
    return ProbeResult.success(probe_name, message)


def cpu_limit_is_configured(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the container CPU quota is limited to one CPU."""
    probe_name = "resources__cpu_limit_is_configured"
    cgroup_v2_cpu_path = Path("/sys/fs/cgroup/cpu.max")

    if cgroup_v2_cpu_path.exists():
        try:
            raw_cpu_limit = cgroup_v2_cpu_path.read_text(encoding="utf-8").strip()
        except OSError as error:
            message = (
                f"Could not read {cgroup_v2_cpu_path}: {type(error).__name__}: {error}"
            )
            return ProbeResult.failure(probe_name, message)

        fields = raw_cpu_limit.split()

        if len(fields) != 2:
            message = f"Invalid CPU limit {raw_cpu_limit!r} at {cgroup_v2_cpu_path}."
            return ProbeResult.failure(probe_name, message)

        raw_quota, raw_period = fields

        if raw_quota == "max":
            message = f"CPU quota is unlimited at {cgroup_v2_cpu_path}."
            return ProbeResult.failure(probe_name, message)

        try:
            quota = int(raw_quota)
            period = int(raw_period)
        except ValueError:
            message = f"Invalid CPU limit {raw_cpu_limit!r} at {cgroup_v2_cpu_path}."
            return ProbeResult.failure(probe_name, message)

        return _cpu_quota_is_one_cpu(
            probe_name=probe_name,
            quota=quota,
            period=period,
        )

    cgroup_v1_quota_path = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    cgroup_v1_period_path = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")

    if not cgroup_v1_quota_path.exists() or not cgroup_v1_period_path.exists():
        message = "Could not find cgroup v2 or cgroup v1 CPU quota files."
        return ProbeResult.failure(probe_name, message)

    quota, quota_error = _read_cgroup_integer(
        probe_name=probe_name,
        cgroup_path=cgroup_v1_quota_path,
        resource_name="CPU quota",
    )

    if quota_error is not None:
        return quota_error

    period, period_error = _read_cgroup_integer(
        probe_name=probe_name,
        cgroup_path=cgroup_v1_period_path,
        resource_name="CPU period",
    )

    if period_error is not None:
        return period_error

    if quota is None or period is None:
        message = "Could not determine cgroup v1 CPU quota and period."
        return ProbeResult.failure(probe_name, message)

    return _cpu_quota_is_one_cpu(
        probe_name=probe_name,
        quota=quota,
        period=period,
    )


def open_file_descriptor_limit_is_configured(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the process soft and hard open-file limits are 256."""
    probe_name = "resources__open_file_descriptor_limit_is_configured"
    expected_limit = 256
    process_limits_path = Path("/proc/self/limits")

    try:
        process_limits = process_limits_path.read_text(encoding="utf-8")
    except OSError as error:
        message = (
            f"Could not read {process_limits_path}: {type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    matching_lines = [
        line
        for line in process_limits.splitlines()
        if line.startswith("Max open files")
    ]

    if not matching_lines:
        message = f"Max open files limit was not found in {process_limits_path}."
        return ProbeResult.failure(probe_name, message)

    if len(matching_lines) > 1:
        message = f"Multiple Max open files limits found in {process_limits_path}."
        return ProbeResult.failure(probe_name, message)

    fields = matching_lines[0].split()

    if len(fields) != 6 or fields[:3] != ["Max", "open", "files"]:
        message = f"Malformed Max open files limit: {matching_lines[0]!r}."
        return ProbeResult.failure(probe_name, message)

    raw_soft_limit = fields[3]
    raw_hard_limit = fields[4]

    try:
        soft_limit = int(raw_soft_limit)
        hard_limit = int(raw_hard_limit)
    except ValueError:
        message = (
            "Open file descriptor limits must be numeric; "
            f"got soft={raw_soft_limit!r}, hard={raw_hard_limit!r}."
        )
        return ProbeResult.failure(probe_name, message)

    if soft_limit != expected_limit or hard_limit != expected_limit:
        message = (
            f"Expected open file descriptor limits {expected_limit}:{expected_limit}, "
            f"got {soft_limit}:{hard_limit}."
        )
        return ProbeResult.failure(probe_name, message)

    message = f"Open file descriptor soft and hard limits are both {expected_limit}."
    return ProbeResult.success(probe_name, message)


def per_user_process_limit_is_configured(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the process soft and hard per-user process limits are 64."""
    probe_name = "resources__per_user_process_limit_is_configured"
    expected_limit = 64
    process_limits_path = Path("/proc/self/limits")

    try:
        process_limits = process_limits_path.read_text(encoding="utf-8")
    except OSError as error:
        message = (
            f"Could not read {process_limits_path}: {type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    matching_lines = [
        line for line in process_limits.splitlines() if line.startswith("Max processes")
    ]

    if not matching_lines:
        message = f"Max processes limit was not found in {process_limits_path}."
        return ProbeResult.failure(probe_name, message)

    if len(matching_lines) > 1:
        message = f"Multiple Max processes limits found in {process_limits_path}."
        return ProbeResult.failure(probe_name, message)

    fields = matching_lines[0].split()

    if len(fields) != 5 or fields[:2] != ["Max", "processes"]:
        message = f"Malformed Max processes limit: {matching_lines[0]!r}."
        return ProbeResult.failure(probe_name, message)

    raw_soft_limit = fields[2]
    raw_hard_limit = fields[3]

    try:
        soft_limit = int(raw_soft_limit)
        hard_limit = int(raw_hard_limit)
    except ValueError:
        message = (
            "Per-user process limits must be numeric; "
            f"got soft={raw_soft_limit!r}, hard={raw_hard_limit!r}."
        )
        return ProbeResult.failure(probe_name, message)

    if soft_limit != expected_limit or hard_limit != expected_limit:
        message = (
            f"Expected per-user process limits {expected_limit}:{expected_limit}, "
            f"got {soft_limit}:{hard_limit}."
        )
        return ProbeResult.failure(probe_name, message)

    message = f"Per-user process soft and hard limits are both {expected_limit}."
    return ProbeResult.success(probe_name, message)


def file_size_limit_is_configured(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the process soft and hard file-size limits are 1 MiB."""
    probe_name = "resources__file_size_limit_is_configured"
    expected_limit = 1_048_576
    process_limits_path = Path("/proc/self/limits")

    try:
        process_limits = process_limits_path.read_text(encoding="utf-8")
    except OSError as error:
        message = (
            f"Could not read {process_limits_path}: {type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    matching_lines = [
        line for line in process_limits.splitlines() if line.startswith("Max file size")
    ]

    if not matching_lines:
        message = f"Max file size limit was not found in {process_limits_path}."
        return ProbeResult.failure(probe_name, message)

    if len(matching_lines) > 1:
        message = f"Multiple Max file size limits found in {process_limits_path}."
        return ProbeResult.failure(probe_name, message)

    fields = matching_lines[0].split()

    if (
        len(fields) != 6
        or fields[:3] != ["Max", "file", "size"]
        or fields[5] != "bytes"
    ):
        message = f"Malformed Max file size limit: {matching_lines[0]!r}."
        return ProbeResult.failure(probe_name, message)

    raw_soft_limit = fields[3]
    raw_hard_limit = fields[4]

    try:
        soft_limit = int(raw_soft_limit)
        hard_limit = int(raw_hard_limit)
    except ValueError:
        message = (
            "File-size limits must be numeric; "
            f"got soft={raw_soft_limit!r}, hard={raw_hard_limit!r}."
        )
        return ProbeResult.failure(probe_name, message)

    if soft_limit != expected_limit or hard_limit != expected_limit:
        message = (
            f"Expected file-size limits {expected_limit}:{expected_limit} bytes, "
            f"got {soft_limit}:{hard_limit} bytes."
        )
        return ProbeResult.failure(probe_name, message)

    message = f"File-size soft and hard limits are both {expected_limit} bytes."
    return ProbeResult.success(probe_name, message)


def _cpu_quota_is_one_cpu(
    probe_name: str,
    quota: int,
    period: int,
) -> ProbeResult:
    if quota <= 0 or period <= 0:
        message = f"CPU quota and period must be positive; got {quota} and {period}."
        return ProbeResult.failure(probe_name, message)

    if quota != period:
        cpu_limit = quota / period
        message = f"Expected CPU limit 1.0, got {cpu_limit:g}."
        return ProbeResult.failure(probe_name, message)

    message = f"CPU use is limited to one CPU ({quota}/{period})."
    return ProbeResult.success(probe_name, message)


def _read_cgroup_integer(
    probe_name: str,
    cgroup_path: Path,
    resource_name: str,
) -> tuple[int | None, ProbeResult | None]:
    try:
        raw_value = cgroup_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        message = f"Could not read {cgroup_path}: {type(error).__name__}: {error}"
        return None, ProbeResult.failure(probe_name, message)

    if raw_value == "max":
        message = f"The {resource_name} is unlimited at {cgroup_path}."
        return None, ProbeResult.failure(probe_name, message)

    try:
        value = int(raw_value)
    except ValueError:
        message = f"Invalid {resource_name} {raw_value!r} at {cgroup_path}."
        return None, ProbeResult.failure(probe_name, message)

    return value, None


RESOURCE_PROBES = ProbeGroup(
    name="resources",
    probes=(
        process_limit_is_configured,
        memory_limit_is_configured,
        additional_swap_is_disabled,
        cpu_limit_is_configured,
        open_file_descriptor_limit_is_configured,
        per_user_process_limit_is_configured,
        file_size_limit_is_configured,
    ),
)
