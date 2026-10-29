import errno
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from metisa_probes._kernel import _landlock_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction


@pytest.mark.parametrize(
    "probe,operation",
    [
        (probes.unlisted_file_read_is_denied, "open"),
        (probes.unlisted_directory_enumeration_is_denied, "scandir"),
    ],
)
@pytest.mark.parametrize(
    "outcome,passed",
    [
        ("denied", True),
        ("allowed", False),
        ("wrong_errno", False),
        ("missing", False),
        ("bad_canary", False),
        ("stat_error", False),
    ],
)
def test_landlock_requires_valid_canary_and_policy_denial(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    operation: str,
    outcome: str,
    passed: bool,
) -> None:
    mode = stat.S_IFREG | stat.S_IROTH if operation == "open" else stat.S_IFDIR | 0o755
    if outcome == "bad_canary":
        mode = stat.S_IFREG if operation == "open" else stat.S_IFREG | 0o644
    metadata = Mock(return_value=SimpleNamespace(st_mode=mode))
    if outcome == "stat_error":
        metadata.side_effect = OSError("cannot inspect canary")
    monkeypatch.setattr(Path, "stat", metadata)
    action = Mock(return_value=42 if operation == "open" else MagicMock())
    errors = {
        "denied": PermissionError(errno.EACCES, "policy denied"),
        "wrong_errno": PermissionError(errno.EPERM, "different denial"),
        "missing": FileNotFoundError(errno.ENOENT, "missing canary"),
    }
    action.side_effect = errors.get(outcome)
    monkeypatch.setattr(probes.os, operation, action)
    close = Mock()
    monkeypatch.setattr(probes.os, "close", close)
    result = probe(probe_context)
    assert result.passed is passed, result.message
    if operation == "open" and outcome == "allowed":
        close.assert_called_once_with(42)
