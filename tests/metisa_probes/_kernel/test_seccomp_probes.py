import errno
import json
from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from metisa_probes._kernel import _seccomp_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction


@pytest.mark.parametrize(
    "text,passed",
    [
        ("Seccomp:\t2\n", True),
        ("Seccomp: 0", False),
        ("Seccomp: 1", False),
        ("Seccomp: bad", False),
        ("", False),
    ],
)
def test_seccomp_filter_mode(
    read_text: Mock, probe_context: ProbeContext, text: str, passed: bool
) -> None:
    read_text.return_value = text
    assert probes.seccomp_filtering_is_active(probe_context).passed is passed


def test_seccomp_status_read_failure(
    read_text: Mock, probe_context: ProbeContext
) -> None:
    read_text.side_effect = OSError("status unavailable")
    assert not probes.seccomp_filtering_is_active(probe_context).passed


@pytest.mark.parametrize(
    "outcome,passed",
    [
        ("denied", True),
        ("allowed", False),
        ("wrong_errno", False),
        ("unavailable", False),
    ],
)
def test_getpriority_denial(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    outcome: str,
    passed: bool,
) -> None:
    operation = Mock(return_value=0)
    if outcome in ("denied", "wrong_errno"):
        operation.side_effect = OSError(
            errno.EACCES if outcome == "denied" else errno.EPERM, "denied"
        )
    monkeypatch.setattr(
        probes.os,
        "getpriority",
        None if outcome == "unavailable" else operation,
        raising=False,
    )
    monkeypatch.setattr(probes.os, "PRIO_PROCESS", 0, raising=False)
    assert probes.custom_getpriority_rule_is_enforced(probe_context).passed is passed


@pytest.mark.parametrize(
    "probe,syscall",
    [
        (probes.custom_ptrace_rule_is_enforced, "ptrace"),
        (probes.custom_process_vm_readv_rule_is_enforced, "process_vm_readv"),
        (probes.custom_process_vm_writev_rule_is_enforced, "process_vm_writev"),
    ],
)
@pytest.mark.parametrize(
    "mode",
    [
        "denied",
        "allowed",
        "wrong_errno",
        "bad_json",
        "wrong_syscall",
        "bad_number",
        "exit_error",
        "spawn_error",
    ],
)
def test_syscall_helper(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    syscall: str,
    mode: str,
) -> None:
    monkeypatch.setattr(probes, "permit_process_spawn", nullcontext)
    payload = {"syscall": syscall, "result": -1, "errno": errno.EACCES}
    if mode == "allowed":
        payload["result"] = 0
    elif mode == "wrong_errno":
        payload["errno"] = errno.EPERM
    elif mode == "wrong_syscall":
        payload["syscall"] = "different"
    elif mode == "bad_number":
        payload["result"] = True
    completed = Mock(
        returncode=1 if mode == "exit_error" else 0,
        stdout="not JSON" if mode == "bad_json" else json.dumps(payload),
    )
    run = Mock(return_value=completed)
    if mode == "spawn_error":
        run.side_effect = OSError("helper unavailable")
    monkeypatch.setattr(probes.subprocess, "run", run)
    result = probe(probe_context)
    assert result.passed is (mode == "denied"), result.message
    assert run.call_args.args[0] == ["/usr/local/bin/metisa-seccomp-probe", syscall]
