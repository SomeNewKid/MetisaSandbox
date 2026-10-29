from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from metisa_probes._probe_models import ProbeContext, ProbeFunction
from metisa_probes._python import _process_probes as probes


@pytest.mark.parametrize(
    "probe,helper",
    [
        (probes.subprocess_popen_is_denied, "_start_with_subprocess_popen"),
        (probes.subprocess_run_is_denied, None),
        (probes.subprocess_call_is_denied, None),
        (probes.subprocess_check_call_is_denied, None),
        (probes.subprocess_check_output_is_denied, None),
        (probes.os_system_is_denied, None),
        (probes.os_popen_is_denied, "_start_with_os_popen"),
        (probes.pty_spawn_is_denied, "_start_with_pty_spawn"),
        (probes.os_fork_is_denied, "_start_with_os_fork"),
        (probes.os_forkpty_is_denied, "_start_with_os_forkpty"),
        (probes.os_posix_spawn_is_denied, "_start_with_os_posix_spawn"),
        (probes.os_posix_spawnp_is_denied, "_start_with_os_posix_spawnp"),
    ],
)
@pytest.mark.parametrize("mode", ["denied", "allowed", "unexpected"])
def test_process_operations(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    helper: str | None,
    mode: str,
) -> None:
    action = Mock(
        side_effect=PermissionError("policy")
        if mode == "denied"
        else RuntimeError("broken API")
        if mode == "unexpected"
        else None
    )
    if helper:
        monkeypatch.setattr(probes, helper, action)
    else:
        name = probe.__name__.removesuffix("_is_denied")
        if name.startswith("subprocess_"):
            monkeypatch.setattr(
                probes.subprocess, name.removeprefix("subprocess_"), action
            )
        else:
            monkeypatch.setattr(probes.os, "system", action)
    result = probe(probe_context)
    assert result.passed is (mode == "denied"), result.message
    action.assert_called_once()


@pytest.mark.parametrize("mode", ["denied", "allowed", "unexpected", "mixed"])
def test_spawn_family(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, mode: str
) -> None:
    denied = Mock(side_effect=PermissionError("policy"))
    other = Mock(
        side_effect=RuntimeError("broken API") if mode == "unexpected" else None
    )
    operations = (
        ("spawnv", denied if mode != "allowed" else other),
        ("spawnve", denied if mode == "denied" else other),
    )
    monkeypatch.setattr(probes, "_get_spawn_operations", lambda: operations)
    result = probes.os_spawn_family_is_denied(probe_context)
    assert result.passed is (mode == "denied"), result.message
    for _, operation in operations:
        assert operation.called


@pytest.mark.parametrize(
    "code,passed", [(0, True), (73, False), (74, False), (126, False)]
)
def test_exec_family_child_status(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    code: int,
    passed: bool,
) -> None:
    monkeypatch.setattr(probes, "permit_process_spawn", nullcontext)
    for name in probes._EXEC_FUNCTION_NAMES:
        monkeypatch.setattr(probes.os, name, Mock(), raising=False)
    run = Mock(return_value=Mock(returncode=code, stderr="child diagnostic"))
    monkeypatch.setattr(probes.subprocess, "run", run)
    result = probes.os_exec_family_is_denied(probe_context)
    assert result.passed is passed, result.message
    assert run.call_count == 8
    for call in run.call_args_list:
        assert call.kwargs["env"]["METISA_RUNTIME_ROLE"] == "workload"
        assert call.args[0][1:4] == ["-I", "-B", "-c"]


@pytest.mark.parametrize("mode", ["missing_api", "spawn_error"])
def test_exec_family_unavailable(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, mode: str
) -> None:
    monkeypatch.setattr(probes, "permit_process_spawn", nullcontext)
    for name in probes._EXEC_FUNCTION_NAMES:
        monkeypatch.setattr(
            probes.os, name, None if mode == "missing_api" else Mock(), raising=False
        )
    run = Mock(side_effect=OSError("cannot start helper"))
    monkeypatch.setattr(probes.subprocess, "run", run)
    assert not probes.os_exec_family_is_denied(probe_context).passed
    if mode == "missing_api":
        run.assert_not_called()
