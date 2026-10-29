import pytest

from metisa_probes._probe_models import ProbeContext
from metisa_probes._python import _diagnostic_probes as probes


def test_purelib_diagnostic(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext
) -> None:
    monkeypatch.setattr(
        probes.sysconfig, "get_path", lambda name: "/opt/metisa-venv/lib/site-packages"
    )
    result = probes.purelib_path(probe_context)
    assert result.passed
    assert result.name == "python__diagnostic__purelib_path"
    assert "/opt/metisa-venv/lib/site-packages" in result.message
