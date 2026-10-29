from pathlib import Path
from unittest.mock import Mock

import pytest

from metisa_probes._container import _browser_probes as probes
from metisa_probes._probe_models import ProbeContext


@pytest.mark.parametrize(
    "argument",
    [
        None,
        "--remote-debugging-port=9222",
        "--remote-debugging-address=0.0.0.0",
        "--remote-debugging-pipe",
        "--start-debugger-server",
        "--marionette",
    ],
)
def test_command_line_arguments(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, argument: str | None
) -> None:
    monkeypatch.setattr(
        Path, "iterdir", lambda self: iter([Path("/proc/12"), Path("/proc/net")])
    )
    command = b"browser\0" + (argument or "--headless").encode()
    monkeypatch.setattr(Path, "read_bytes", lambda self: command)
    result = probes.debugging_command_line_is_absent(probe_context)
    assert result.passed is (argument is None)
    if argument:
        assert "PID 12" in result.message


@pytest.mark.parametrize(
    "error,passed", [(FileNotFoundError(), True), (PermissionError(), False)]
)
def test_disappearing_vs_unreadable_process(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    error: OSError,
    passed: bool,
) -> None:
    monkeypatch.setattr(Path, "iterdir", lambda self: iter([Path("/proc/12")]))
    monkeypatch.setattr(Path, "read_bytes", Mock(side_effect=error))
    assert probes.debugging_command_line_is_absent(probe_context).passed is passed


def test_process_enumeration_failure(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext
) -> None:
    monkeypatch.setattr(Path, "iterdir", Mock(side_effect=OSError("proc unavailable")))
    assert not probes.debugging_command_line_is_absent(probe_context).passed


@pytest.mark.parametrize(
    "variable",
    [None, "BROWSER_WS_ENDPOINT", "CDP_ENDPOINT", "CDP_URL", "PLAYWRIGHT_CDP_URL"],
)
def test_debugging_environment(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, variable: str | None
) -> None:
    monkeypatch.setattr(
        probes.os, "environ", {} if variable is None else {variable: ""}
    )
    assert probes.debugging_environment_is_absent(probe_context).passed is (
        variable is None
    )
