from unittest.mock import Mock

import pytest

from metisa_probes._container import _system_command_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction


@pytest.mark.parametrize(
    "probe", probes.SYSTEM_COMMAND_PROBES.probes, ids=lambda p: p.__name__
)
@pytest.mark.parametrize("location", ["absent", "path", "outside_path"])
def test_commands_must_be_absent(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    location: str,
) -> None:
    which = Mock(return_value="/custom/bin/command" if location == "path" else None)
    monkeypatch.setattr(probes.shutil, "which", which)
    monkeypatch.setattr(
        probes.os.path, "lexists", lambda path: location == "outside_path"
    )
    result = probe(probe_context)
    assert result.passed is (location == "absent"), result.message
    command = which.call_args.args[0]
    assert command in result.message
