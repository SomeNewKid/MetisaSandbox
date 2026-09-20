"""Probes of the file system."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
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


def source_control_metadata_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the staged source contains no Git metadata."""
    return _forbidden_source_entries_are_absent(
        probe_name="filesystem__source_control_metadata_is_absent",
        source_path=Path(probe_context.source_volume),
        description="Git metadata",
        is_forbidden=lambda path: path.name == ".git",
    )


def development_directories_are_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the staged source contains no development directories."""
    directory_names = {
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "script",
        "scripts",
        "tests",
    }
    return _forbidden_source_entries_are_absent(
        probe_name="filesystem__development_directories_are_absent",
        source_path=Path(probe_context.source_volume),
        description="development directories",
        is_forbidden=lambda path: path.is_dir() and path.name in directory_names,
    )


def host_sandbox_module_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the host-only metisa_sandbox module is not staged."""
    return _forbidden_source_entries_are_absent(
        probe_name="filesystem__host_sandbox_module_is_absent",
        source_path=Path(probe_context.source_volume),
        description="host-only metisa_sandbox modules",
        is_forbidden=lambda path: path.is_dir() and path.name == "metisa_sandbox",
    )


def generated_python_artifacts_are_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the staged source contains no generated Python artifacts."""
    return _forbidden_source_entries_are_absent(
        probe_name="filesystem__generated_python_artifacts_are_absent",
        source_path=Path(probe_context.source_volume),
        description="generated Python artifacts",
        is_forbidden=_is_generated_python_artifact,
    )


def project_configuration_files_are_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the staged source contains no project configuration files."""
    file_names = {
        "pyproject.toml",
        "requirements.txt",
        "setup.cfg",
        "setup.py",
        "tox.ini",
    }
    return _forbidden_source_entries_are_absent(
        probe_name="filesystem__project_configuration_files_are_absent",
        source_path=Path(probe_context.source_volume),
        description="project configuration files",
        is_forbidden=lambda path: path.is_file() and path.name in file_names,
    )


def sandbox_home_directory_is_not_writable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the sandbox account's home directory is not writable."""
    probe_name = "filesystem__sandbox_home_directory_is_not_writable"

    try:
        home_path = _get_sandbox_home_directory()
    except (OSError, ValueError) as error:
        message = f"Could not determine sandbox home: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    if not home_path.is_dir():
        message = f"Sandbox home directory was not found at {home_path}."
        return ProbeResult.failure(probe_name, message)

    return _directory_tree_is_not_writable(
        probe_name=probe_name,
        directory_path=home_path,
    )


def effective_home_directory_is_not_writable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify HOME does not redirect software to a writable location."""
    probe_name = "filesystem__effective_home_directory_is_not_writable"

    try:
        account_home_path = _get_sandbox_home_directory()
    except (OSError, ValueError) as error:
        message = f"Could not determine sandbox home: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    configured_home = os.environ.get("HOME")
    effective_home_path = (
        Path(configured_home) if configured_home is not None else account_home_path
    )

    if effective_home_path != account_home_path:
        message = (
            f"HOME resolves to {effective_home_path}, "
            f"not sandbox account home {account_home_path}."
        )
        return ProbeResult.failure(probe_name, message)

    return _directory_tree_is_not_writable(
        probe_name=probe_name,
        directory_path=effective_home_path,
    )


def effective_xdg_config_directory_is_not_writable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the effective XDG configuration directory is not writable."""
    return _effective_xdg_directory_is_not_writable(
        probe_name="filesystem__effective_xdg_config_directory_is_not_writable",
        environment_variable="XDG_CONFIG_HOME",
        default_child_directory=".config",
    )


def effective_xdg_cache_directory_is_not_writable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the effective XDG cache directory is not writable."""
    return _effective_xdg_directory_is_not_writable(
        probe_name="filesystem__effective_xdg_cache_directory_is_not_writable",
        environment_variable="XDG_CACHE_HOME",
        default_child_directory=".cache",
    )


def effective_xdg_runtime_directory_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify no XDG runtime directory is configured for the workload."""
    probe_name = "filesystem__effective_xdg_runtime_directory_is_absent"
    environment_variable = "XDG_RUNTIME_DIR"

    if environment_variable in os.environ:
        configured_path = os.environ[environment_variable]
        message = f"{environment_variable} is configured as {configured_path!r}."
        return ProbeResult.failure(probe_name, message)

    message = f"{environment_variable} is not configured."
    return ProbeResult.success(probe_name, message)


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


def root_filesystem_is_read_only(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the container root filesystem is mounted read-only."""
    probe_name = "filesystem__root_filesystem_is_read_only"
    mountinfo_path = Path("/proc/self/mountinfo")

    try:
        mountinfo = mountinfo_path.read_text(encoding="utf-8")
    except OSError as error:
        message = f"Could not read {mountinfo_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    for entry in mountinfo.splitlines():
        fields = entry.split()

        if len(fields) < 7 or "-" not in fields:
            message = f"Malformed mount entry in {mountinfo_path}: {entry!r}."
            return ProbeResult.failure(probe_name, message)

        mount_point = fields[4]

        if mount_point != "/":
            continue

        mount_options = set(fields[5].split(","))

        if "ro" not in mount_options:
            options = ",".join(sorted(mount_options))
            message = f"Root filesystem is not read-only; mount options: {options}."
            return ProbeResult.failure(probe_name, message)

        message = "Root filesystem is mounted read-only."
        return ProbeResult.success(probe_name, message)

    message = f"Root filesystem mount was not found in {mountinfo_path}."
    return ProbeResult.failure(probe_name, message)


def tmp_directory_is_hardened_tmpfs(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify /tmp is a writable, restricted 16 MiB tmpfs mount."""
    return _writable_tmpfs_is_hardened(
        probe_name="filesystem__tmp_directory_is_hardened_tmpfs",
        mount_path=Path("/tmp"),
        expected_size_bytes=16 * 1024 * 1024,
    )


def sandbox_work_location_is_hardened_tmpfs(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify /sandbox-work is a restricted 1 MiB tmpfs mount."""
    return _writable_tmpfs_is_hardened(
        probe_name="filesystem__sandbox_work_location_is_hardened_tmpfs",
        mount_path=Path(probe_context.work_dir),
        expected_size_bytes=1024 * 1024,
    )


def proc_acpi_is_concealed(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify /proc/acpi exposes no contents and rejects writes."""
    return _system_path_is_concealed(
        probe_name="filesystem__proc_acpi_is_concealed",
        system_path=Path("/proc/acpi"),
    )


def sys_firmware_is_concealed(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify /sys/firmware exposes no contents and rejects writes."""
    return _system_path_is_concealed(
        probe_name="filesystem__sys_firmware_is_concealed",
        system_path=Path("/sys/firmware"),
    )


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


def _writable_tmpfs_is_hardened(
    probe_name: str,
    mount_path: Path,
    expected_size_bytes: int,
) -> ProbeResult:
    mountinfo_path = Path("/proc/self/mountinfo")
    required_options = {"rw", "nosuid", "nodev", "noexec"}

    try:
        mountinfo = mountinfo_path.read_text(encoding="utf-8")
    except OSError as error:
        message = f"Could not read {mountinfo_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    for entry in mountinfo.splitlines():
        fields = entry.split()

        if len(fields) < 7 or "-" not in fields:
            message = f"Malformed mount entry in {mountinfo_path}: {entry!r}."
            return ProbeResult.failure(probe_name, message)

        if fields[4] != str(mount_path):
            continue

        separator_index = fields.index("-")

        if len(fields) <= separator_index + 3:
            message = (
                f"Malformed {mount_path} mount entry in {mountinfo_path}: {entry!r}."
            )
            return ProbeResult.failure(probe_name, message)

        filesystem_type = fields[separator_index + 1]

        if filesystem_type != "tmpfs":
            message = f"Expected {mount_path} to use tmpfs, found {filesystem_type!r}."
            return ProbeResult.failure(probe_name, message)

        mount_options = set(fields[5].split(","))
        missing_options = sorted(required_options - mount_options)

        if missing_options:
            options = ", ".join(missing_options)
            message = f"The {mount_path} mount is missing required options: {options}."
            return ProbeResult.failure(probe_name, message)

        try:
            actual_size_bytes = shutil.disk_usage(mount_path).total
        except OSError as error:
            message = f"Could not inspect {mount_path}: {type(error).__name__}: {error}"
            return ProbeResult.failure(probe_name, message)

        if actual_size_bytes != expected_size_bytes:
            message = (
                f"Expected {mount_path} capacity to be {expected_size_bytes} bytes, "
                f"found {actual_size_bytes} bytes."
            )
            return ProbeResult.failure(probe_name, message)

        probe_file = mount_path / ".probe-write-test"

        try:
            probe_file.write_text(probe_name, encoding="utf-8")
            probe_file.unlink()
        except OSError as error:
            message = (
                f"Could not write to {mount_path}: {type(error).__name__}: {error}"
            )
            return ProbeResult.failure(probe_name, message)

        size_mib = expected_size_bytes // (1024 * 1024)
        message = (
            f"{mount_path} is a writable {size_mib} MiB tmpfs with "
            "nosuid, nodev, and noexec."
        )
        return ProbeResult.success(probe_name, message)

    message = f"The {mount_path} mount was not found in {mountinfo_path}."
    return ProbeResult.failure(probe_name, message)


def _system_path_is_concealed(
    probe_name: str,
    system_path: Path,
) -> ProbeResult:
    if not system_path.is_dir():
        message = f"Expected system path is not a directory: {system_path}."
        return ProbeResult.failure(probe_name, message)

    try:
        exposed_entries = sorted(path.name for path in system_path.iterdir())
    except OSError as error:
        message = f"Could not inspect {system_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    if exposed_entries:
        entries = ", ".join(exposed_entries)
        message = f"System path {system_path} exposes entries: {entries}."
        return ProbeResult.failure(probe_name, message)

    probe_file = system_path / ".probe-write-test"

    try:
        probe_file.write_text(probe_name, encoding="utf-8")
    except OSError as error:
        message = (
            f"System path {system_path} exposes no contents and rejected writes: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.success(probe_name, message)

    probe_file.unlink(missing_ok=True)
    message = f"System path {system_path} permitted file creation."
    return ProbeResult.failure(probe_name, message)


def _forbidden_source_entries_are_absent(
    probe_name: str,
    source_path: Path,
    description: str,
    is_forbidden: Callable[[Path], bool],
) -> ProbeResult:
    if not source_path.is_dir():
        message = f"Staged source directory was not found at {source_path}."
        return ProbeResult.failure(probe_name, message)

    try:
        forbidden_entries = sorted(
            (
                path.relative_to(source_path)
                for path in source_path.rglob("*")
                if is_forbidden(path)
            ),
            key=str,
        )
    except OSError as error:
        message = f"Could not inspect {source_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    if forbidden_entries:
        entries = ", ".join(str(path) for path in forbidden_entries)
        message = f"Staged source contains {description}: {entries}."
        return ProbeResult.failure(probe_name, message)

    message = f"Staged source contains no {description}."
    return ProbeResult.success(probe_name, message)


def _is_generated_python_artifact(path: Path) -> bool:
    if not path.is_dir():
        return False

    return (
        path.name == "__pycache__"
        or path.name.endswith(".egg-info")
        or path.name.endswith(".dist-info")
    )


def _get_sandbox_home_directory() -> Path:
    passwd_path = Path("/etc/passwd")
    passwd_contents = passwd_path.read_text(encoding="utf-8")
    matching_home_directories: list[str] = []

    for line in passwd_contents.splitlines():
        fields = line.split(":")

        if len(fields) == 7 and fields[0] == "sandbox":
            matching_home_directories.append(fields[5])

    if not matching_home_directories:
        raise ValueError("sandbox account was not found in /etc/passwd")

    if len(matching_home_directories) > 1:
        raise ValueError("multiple sandbox account entries found in /etc/passwd")

    home_directory = matching_home_directories[0]

    if not home_directory:
        raise ValueError("sandbox account has no configured home directory")

    home_path = Path(home_directory)

    if not home_path.is_absolute():
        raise ValueError(f"sandbox account home is not absolute: {home_directory!r}")

    return home_path


def _effective_xdg_directory_is_not_writable(
    probe_name: str,
    environment_variable: str,
    default_child_directory: str,
) -> ProbeResult:
    configured_path = os.environ.get(environment_variable)

    if configured_path is not None:
        directory_path = Path(configured_path)

        if not directory_path.is_absolute():
            message = f"{environment_variable} is not absolute: {configured_path!r}."
            return ProbeResult.failure(probe_name, message)
    else:
        try:
            home_path = _get_sandbox_home_directory()
        except (OSError, ValueError) as error:
            message = (
                f"Could not determine sandbox home: {type(error).__name__}: {error}"
            )
            return ProbeResult.failure(probe_name, message)

        directory_path = home_path / default_child_directory

    return _directory_tree_is_not_writable(
        probe_name=probe_name,
        directory_path=directory_path,
    )


def _directory_tree_is_not_writable(
    probe_name: str,
    directory_path: Path,
) -> ProbeResult:
    existing_path = directory_path

    while not existing_path.exists() and existing_path != existing_path.parent:
        existing_path = existing_path.parent

    if not existing_path.is_dir():
        message = f"Nearest existing path is not a directory: {existing_path}."
        return ProbeResult.failure(probe_name, message)

    probe_file = existing_path / ".probe-write-test"

    try:
        probe_file.write_text(probe_name, encoding="utf-8")
    except OSError as error:
        message = (
            f"Directory tree for {directory_path} rejected writes at "
            f"{existing_path}: {type(error).__name__}: {error}"
        )
        return ProbeResult.success(probe_name, message)

    probe_file.unlink(missing_ok=True)
    message = f"Directory tree for {directory_path} is writable at {existing_path}."
    return ProbeResult.failure(probe_name, message)


FILESYSTEM_PROBES = ProbeGroup(
    name="filesystem",
    probes=(
        sandbox_output_volume_is_writable,
        sandbox_source_volume_is_not_writable,
        sandbox_source_module_file_is_readable,
        sandbox_source_module_is_not_writable,
        source_control_metadata_is_absent,
        development_directories_are_absent,
        host_sandbox_module_is_absent,
        generated_python_artifacts_are_absent,
        project_configuration_files_are_absent,
        sandbox_home_directory_is_not_writable,
        effective_home_directory_is_not_writable,
        effective_xdg_config_directory_is_not_writable,
        effective_xdg_cache_directory_is_not_writable,
        effective_xdg_runtime_directory_is_absent,
        sandbox_work_location_is_available,
        sandbox_work_location_is_writable,
        root_filesystem_is_read_only,
        tmp_directory_is_hardened_tmpfs,
        sandbox_work_location_is_hardened_tmpfs,
        proc_acpi_is_concealed,
        sys_firmware_is_concealed,
        etc_directory_is_not_writable,
        usr_local_bin_directory_is_not_writable,
    ),
)
