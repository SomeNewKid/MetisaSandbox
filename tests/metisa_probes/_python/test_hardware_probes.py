from pathlib import Path
from unittest.mock import Mock

import pytest

from metisa_probes._probe_models import ProbeContext, ProbeFunction
from metisa_probes._python import _hardware_probes as probes


@pytest.mark.parametrize(
    "probe", probes.HARDWARE_PROBES.probes, ids=lambda p: p.__name__
)
@pytest.mark.parametrize("mode", ["denied", "allowed", "unexpected"])
def test_hardware_policy_denial(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    mode: str,
) -> None:
    action = Mock(return_value=[])
    if mode != "allowed":
        action.side_effect = (
            PermissionError("policy")
            if mode == "denied"
            else FileNotFoundError("missing device")
        )
    for method in ("exists", "iterdir", "glob"):
        monkeypatch.setattr(Path, method, action)
    monkeypatch.setattr(probes.subprocess, "run", action)
    result = probe(probe_context)
    assert result.passed is (mode == "denied"), result.message
    assert result.name.startswith("python__hardware__")
