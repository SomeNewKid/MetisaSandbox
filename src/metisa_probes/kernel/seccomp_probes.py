"""Probes related to Linux seccomp filtering."""

from __future__ import annotations

import errno
import json
import os
import subprocess
from pathlib import Path

from ..probe_models import ProbeContext, ProbeGroup, ProbeResult
from ..python.probe_helpers import permit_process_spawn

_SYSCALL_HELPER_PATH = "/usr/local/bin/metisa-seccomp-probe"


def seccomp_filtering_is_active(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the current process is running in seccomp filter mode."""
    probe_name = "kernel__seccomp__seccomp_filtering_is_active"
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
        if separator == "" or field_name != "Seccomp":
            continue

        value = raw_value.strip()
        if value == "2":
            return ProbeResult.success(probe_name, "Seccomp filter mode is active.")

        message = f"Expected Seccomp value 2, got {value!r}."
        return ProbeResult.failure(probe_name, message)

    message = f"Seccomp field was not found in {process_status_path}."
    return ProbeResult.failure(probe_name, message)


def custom_getpriority_rule_is_enforced(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the custom profile rejects getpriority with EACCES."""
    probe_name = "kernel__seccomp__custom_getpriority_rule_is_enforced"
    getpriority = getattr(os, "getpriority", None)
    prio_process = getattr(os, "PRIO_PROCESS", None)

    if not callable(getpriority) or not isinstance(prio_process, int):
        message = "The getpriority API is unavailable on this platform."
        return ProbeResult.failure(probe_name, message)

    try:
        getpriority(prio_process, 0)
    except OSError as error:
        if error.errno == errno.EACCES:
            message = "getpriority was rejected with EACCES as expected."
            return ProbeResult.success(probe_name, message)

        message = f"Expected getpriority errno {errno.EACCES}, got {error.errno!r}."
        return ProbeResult.failure(probe_name, message)

    message = "getpriority succeeded; the custom EACCES restriction is not enforced."
    return ProbeResult.failure(probe_name, message)


def custom_ptrace_rule_is_enforced(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the custom profile rejects ptrace with EACCES."""
    return _check_custom_syscall_rule("ptrace")


def custom_process_vm_readv_rule_is_enforced(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the custom profile rejects process_vm_readv with EACCES."""
    return _check_custom_syscall_rule("process_vm_readv")


def custom_process_vm_writev_rule_is_enforced(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the custom profile rejects process_vm_writev with EACCES."""
    return _check_custom_syscall_rule("process_vm_writev")


def _check_custom_syscall_rule(syscall_name: str) -> ProbeResult:
    probe_name = f"kernel__seccomp__custom_{syscall_name}_rule_is_enforced"
    arguments = [_SYSCALL_HELPER_PATH, syscall_name]

    try:
        with permit_process_spawn():
            result = subprocess.run(
                arguments,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
        message = f"Could not run syscall helper: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    if result.returncode != 0:
        message = f"Syscall helper exited with code {result.returncode}."
        return ProbeResult.failure(probe_name, message)

    try:
        payload = json.loads(result.stdout)
    except ValueError:
        return ProbeResult.failure(probe_name, "Syscall helper returned invalid JSON.")

    if not isinstance(payload, dict) or payload.get("syscall") != syscall_name:
        return ProbeResult.failure(
            probe_name, "Syscall helper returned an invalid result."
        )

    syscall_result = payload.get("result")
    syscall_errno = payload.get("errno")
    if type(syscall_result) is not int or type(syscall_errno) is not int:
        return ProbeResult.failure(
            probe_name, "Syscall helper returned invalid numbers."
        )

    if syscall_result == -1 and syscall_errno == errno.EACCES:
        message = f"{syscall_name} was rejected with EACCES as expected."
        return ProbeResult.success(probe_name, message)

    message = (
        f"Expected {syscall_name} result -1 and errno {errno.EACCES}, "
        f"got result {syscall_result} and errno {syscall_errno}."
    )
    return ProbeResult.failure(probe_name, message)


SECCOMP_PROBES = ProbeGroup(
    name="seccomp",
    probes=(
        seccomp_filtering_is_active,
        custom_getpriority_rule_is_enforced,
        custom_ptrace_rule_is_enforced,
        custom_process_vm_readv_rule_is_enforced,
        custom_process_vm_writev_rule_is_enforced,
    ),
)
