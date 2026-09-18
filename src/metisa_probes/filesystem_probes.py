"""Probes of the file system."""

from __future__ import annotations

from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult


def sandbox_output_volume_is_writable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the configured output volume is writable."""
    probe_name = "filesystem__sandbox_output_volume_is_writable"
    output_volume = Path(probe_context.output_volume)
    probe_file = output_volume / ".probe-write-test"

    try:
        probe_file.write_text(probe_name, encoding="utf-8")
        if not probe_file.exists():
            return ProbeResult.failure(probe_name, f"File not created at {probe_file}.")
        probe_file.unlink()
    except OSError as error:
        return ProbeResult.failure(probe_name, str(error))

    return ProbeResult.success(probe_name, f"File created at {probe_file}")


def sandbox_source_volume_is_not_writable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the configured source volume is not writable."""
    probe_name = "filesystem__sandbox_source_volume_is_not_writable"
    source_volume = Path(probe_context.source_volume)
    probe_file = source_volume / ".probe-write-test"

    try:
        probe_file.write_text(probe_name, encoding="utf-8")
        if probe_file.exists():
            probe_file.unlink()
            return ProbeResult.failure(probe_name, f"File created at {probe_file}")
    except OSError as error:
        return ProbeResult.success(probe_name, str(error))

    failure_message = f"File creation at {probe_file} did not fail."
    return ProbeResult.failure(probe_name, failure_message)


def sandbox_source_module_file_is_readable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the configured source module files are readable."""
    probe_name = "filesystem__sandbox_source_module_file_is_readable"
    source_volume = Path(probe_context.source_volume)
    probe_file = source_volume / "metisa_probes" / "__init__.py"

    if not probe_file.exists():
        return ProbeResult.failure(probe_name, f"File not found at {probe_file}")

    try:
        content = probe_file.read_text(encoding="utf-8")
        if not content:
            return ProbeResult.failure(probe_name, f"File empty at {probe_file}")

        sniff = "Metisa"
        if sniff not in content:
            failure_message = f"File at {probe_file} did not contain '{sniff}'"
            return ProbeResult.failure(probe_name, failure_message)

        success_message = f"File at {probe_file} did contain '{sniff}'"
        return ProbeResult.success(probe_name, success_message)

    except OSError as error:
        return ProbeResult.failure(probe_name, str(error))


def sandbox_source_module_is_not_writable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the configured source module is not writable."""
    probe_name = "filesystem__sandbox_source_module_is_not_writable"
    source_volume = Path(probe_context.source_volume)
    probe_file = source_volume / "metisa_probes" / ".probe-write-test"

    try:
        probe_file.write_text(probe_name, encoding="utf-8")
        if probe_file.exists():
            probe_file.unlink()
            return ProbeResult.failure(probe_name, f"File created at {probe_file}")
    except OSError as error:
        return ProbeResult.success(probe_name, str(error))

    failure_message = f"File creation at {probe_file} did not fail."
    return ProbeResult.failure(probe_name, failure_message)


def sandbox_work_location_is_available(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the configured work location is writable."""
    probe_name = "filesystem__sandbox_work_location_is_available"
    work_dir_volume = Path(probe_context.work_dir)
    if work_dir_volume.exists():
        success_message = f"Work directory exists at {work_dir_volume}"
        return ProbeResult.success(probe_name, success_message)
    else:
        failure_message = f"Work directory does not exist at {work_dir_volume}"
        return ProbeResult.failure(probe_name, failure_message)


def sandbox_work_location_is_writable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the configured work location is writable."""
    probe_name = "filesystem__sandbox_work_location_is_writable"
    work_dir_volume = Path(probe_context.work_dir)
    probe_file = work_dir_volume / ".probe-write-test"

    try:
        probe_file.write_text(probe_name, encoding="utf-8")
        if not probe_file.exists():
            return ProbeResult.failure(probe_name, f"File not created at {probe_file}.")
        content = probe_file.read_text()
        if not content:
            return ProbeResult.failure(probe_name, f"File empty at {probe_file}.")
        probe_file.unlink()
    except OSError as error:
        return ProbeResult.failure(probe_name, str(error))

    if content != probe_name:
        return ProbeResult.failure(probe_name, f"Unexpected content at {probe_file}.")

    return ProbeResult.success(probe_name, f"File created at {probe_file}")


def etc_directory_is_not_writable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the /etc directory is not writable."""
    probe_name = "filesystem__etc_directory_is_not_writable"
    probe_file = Path("/etc") / ".probe-write-test"

    try:
        probe_file.write_text(probe_name, encoding="utf-8")
        if probe_file.exists():
            probe_file.unlink()
            return ProbeResult.failure(probe_name, f"File created at {probe_file}")
    except OSError as error:
        return ProbeResult.success(probe_name, str(error))

    failure_message = f"File creation at {probe_file} did not fail."
    return ProbeResult.failure(probe_name, failure_message)


def usr_local_bin_directory_is_not_writable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the /usr/local/bin directory is not writable."""
    probe_name = "filesystem__usr_local_bin_directory_is_not_writable"
    probe_file = Path("/usr/local/bin") / ".probe-write-test"

    try:
        probe_file.write_text(probe_name, encoding="utf-8")
        if probe_file.exists():
            probe_file.unlink()
            return ProbeResult.failure(probe_name, f"File created at {probe_file}")
    except OSError as error:
        return ProbeResult.success(probe_name, str(error))

    failure_message = f"File creation at {probe_file} did not fail."
    return ProbeResult.failure(probe_name, failure_message)


FILESYSTEM_PROBES = ProbeGroup(
    name="filesystem",
    probes=(
        sandbox_output_volume_is_writable,
        sandbox_source_volume_is_not_writable,
        sandbox_source_module_file_is_readable,
        sandbox_source_module_is_not_writable,
        sandbox_work_location_is_available,
        sandbox_work_location_is_writable,
        etc_directory_is_not_writable,
        usr_local_bin_directory_is_not_writable,
    ),
)
