from unittest.mock import Mock

import pytest

from metisa_probes._container import _identity_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction


@pytest.mark.parametrize(
    "entry,uid,passed",
    [
        ("sandbox:x:1000:1000::/home/sandbox:/usr/sbin/nologin", 1000, True),
        ("sandbox:x:1000:1000::/home/sandbox:/usr/sbin/nologin", 0, False),
        ("sandbox:x:bad:1000::/home/sandbox:/usr/sbin/nologin", 1000, False),
        ("root:x:0:0::/root:/bin/sh", 1000, False),
        ("sandbox:malformed", 1000, False),
    ],
)
def test_effective_identity(
    monkeypatch: pytest.MonkeyPatch,
    read_text: Mock,
    probe_context: ProbeContext,
    entry: str,
    uid: int,
    passed: bool,
) -> None:
    read_text.return_value = entry
    monkeypatch.setattr(probes.os, "geteuid", lambda: uid, raising=False)
    result = probes.current_user_is_sandbox_user(probe_context)
    assert result.passed is passed
    assert result.name == "container__identity__current_user_is_sandbox_user"


@pytest.mark.parametrize(
    "shell,passed", [("/usr/sbin/nologin", True), ("/bin/sh", False), ("", False)]
)
def test_login_shell(
    read_text: Mock, probe_context: ProbeContext, shell: str, passed: bool
) -> None:
    read_text.return_value = f"sandbox:x:1000:1000::/home/sandbox:{shell}"
    assert probes.sandbox_user_login_shell_is_nologin(probe_context).passed is passed


@pytest.mark.parametrize("probe", probes.IDENTITY_PROBES.probes)
@pytest.mark.parametrize("mode", ["missing", "duplicate", "unreadable"])
def test_invalid_accounts(
    monkeypatch: pytest.MonkeyPatch,
    read_text: Mock,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    mode: str,
) -> None:
    monkeypatch.setattr(probes.os, "geteuid", lambda: 1000, raising=False)
    entry = "sandbox:x:1000:1000::/home/sandbox:/usr/sbin/nologin\n"
    read_text.return_value = entry * 2 if mode == "duplicate" else ""
    if mode == "unreadable":
        read_text.side_effect = OSError("passwd unavailable")
    assert not probe(probe_context).passed


def test_geteuid_unavailable(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext
) -> None:
    monkeypatch.setattr(probes.os, "geteuid", None, raising=False)
    assert not probes.current_user_is_sandbox_user(probe_context).passed
