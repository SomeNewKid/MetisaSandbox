import os
from dataclasses import replace

import pytest

from metisa_probes._container import _environment_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction


@pytest.mark.parametrize(
    "variable",
    [
        None,
        "SSH_AUTH_SOCK",
        "GPG_AGENT_INFO",
        "DBUS_SESSION_BUS_ADDRESS",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
    ],
)
def test_host_channels(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, variable: str | None
) -> None:
    monkeypatch.setattr(os, "environ", {} if variable is None else {variable: ""})
    result = probes.host_channel_environment_is_absent(probe_context)
    assert result.passed is (variable is None)
    if variable:
        assert variable in result.message


@pytest.mark.parametrize(
    "probe,variable,expected",
    [
        (
            probes.declared_literal_environment_is_available,
            "METISA_PROBE_1",
            "hard-coded value",
        ),
        (
            probes.declared_host_environment_is_resolved,
            "METISA_PROBE_2",
            "Retrieved from host's environment variables",
        ),
    ],
)
@pytest.mark.parametrize("mode", ["valid", "wrong", "empty", "missing", "undeclared"])
def test_diagnostic_environment(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    variable: str,
    expected: str,
    mode: str,
) -> None:
    values = (
        {}
        if mode == "missing"
        else {
            variable: expected
            if mode == "valid"
            else ""
            if mode == "empty"
            else "wrong"
        }
    )
    monkeypatch.setattr(os, "environ", values)
    specification = replace(
        probe_context.specification,
        environs=frozenset()
        if mode == "undeclared"
        else frozenset({f"{variable}=declared"}),
    )
    result = probe(replace(probe_context, specification=specification))
    assert result.passed is (mode in ("valid", "undeclared"))
    if mode == "undeclared":
        assert "Skipping" in result.message
