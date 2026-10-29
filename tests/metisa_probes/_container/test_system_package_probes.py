from unittest.mock import Mock

import pytest

from metisa_probes._container import _system_package_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction


@pytest.mark.parametrize(
    "probe", probes.SYSTEM_PACKAGE_PROBES.probes, ids=lambda p: p.__name__
)
@pytest.mark.parametrize("present", [False, True])
def test_package_tools_and_state_must_be_absent(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    present: bool,
) -> None:
    monkeypatch.setattr(probes.shutil, "which", lambda name: None)
    monkeypatch.setattr(probes.os.path, "lexists", lambda path: present)
    result = probe(probe_context)
    assert result.passed is not present, result.message


@pytest.mark.parametrize(
    "probe", probes.SYSTEM_PACKAGE_PROBES.probes[:4], ids=lambda p: p.__name__
)
def test_package_entry_points_on_custom_path(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, probe: ProbeFunction
) -> None:
    monkeypatch.setattr(probes.os.path, "lexists", lambda path: False)
    which = Mock(return_value="/custom/bin/package-tool")
    monkeypatch.setattr(probes.shutil, "which", which)
    assert not probe(probe_context).passed
    which.assert_called_once()
