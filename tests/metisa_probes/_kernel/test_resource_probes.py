from pathlib import Path
from unittest.mock import Mock

import pytest

from metisa_probes._kernel import _resource_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction


@pytest.mark.parametrize(
    "probe,valid",
    [
        (probes.process_limit_is_configured, "64"),
        (probes.memory_limit_is_configured, "134217728"),
        (probes.additional_swap_is_disabled, "0"),
        (probes.cpu_limit_is_configured, "100000 100000"),
    ],
)
@pytest.mark.parametrize(
    "mode", ["valid", "wrong", "unlimited", "malformed", "read_error", "missing"]
)
def test_cgroup_v2_limits(
    monkeypatch: pytest.MonkeyPatch,
    read_text: Mock,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    valid: str,
    mode: str,
) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: mode != "missing")
    read_text.return_value = {
        "valid": valid,
        "wrong": "1",
        "unlimited": "max",
        "malformed": "invalid",
    }.get(mode, valid)
    if mode == "read_error":
        read_text.side_effect = OSError("cgroup unreadable")
    result = probe(probe_context)
    assert result.passed is (mode == "valid"), result.message
    assert result.message


@pytest.mark.parametrize(
    "probe,files",
    [
        (probes.process_limit_is_configured, {"pids/pids.max": "64"}),
        (
            probes.memory_limit_is_configured,
            {"memory/memory.limit_in_bytes": "134217728"},
        ),
        (
            probes.additional_swap_is_disabled,
            {
                "memory/memory.limit_in_bytes": "134217728",
                "memory/memory.memsw.limit_in_bytes": "134217728",
            },
        ),
        (
            probes.cpu_limit_is_configured,
            {"cpu/cpu.cfs_quota_us": "50000", "cpu/cpu.cfs_period_us": "50000"},
        ),
    ],
)
def test_cgroup_v1_fallback(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    files: dict[str, str],
) -> None:
    paths = {Path("/sys/fs/cgroup") / name: value for name, value in files.items()}
    monkeypatch.setattr(Path, "exists", lambda self: self in paths)
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: paths[self])
    assert probe(probe_context).passed


@pytest.mark.parametrize(
    "quota,period,passed",
    [
        (1, 1, True),
        (50000, 100000, False),
        (200000, 100000, False),
        (0, 100000, False),
        (-1, 100000, False),
        (1, 0, False),
    ],
)
def test_cpu_ratio(
    read_text: Mock,
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    quota: int,
    period: int,
    passed: bool,
) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    read_text.return_value = f"{quota} {period}"
    assert probes.cpu_limit_is_configured(probe_context).passed is passed


@pytest.mark.parametrize(
    "probe,label,limit,unit",
    [
        (
            probes.open_file_descriptor_limit_is_configured,
            "Max open files",
            256,
            "files",
        ),
        (probes.per_user_process_limit_is_configured, "Max processes", 64, "processes"),
        (probes.file_size_limit_is_configured, "Max file size", 1048576, "bytes"),
    ],
)
@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "soft",
        "hard",
        "unlimited",
        "missing",
        "duplicate",
        "malformed",
        "read_error",
    ],
)
def test_process_limits(
    read_text: Mock,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    label: str,
    limit: int,
    unit: str,
    mode: str,
) -> None:
    soft = limit + 1 if mode == "soft" else limit
    hard = limit + 1 if mode == "hard" else limit
    if mode == "unlimited":
        text = f"{label} unlimited unlimited {unit}"
    else:
        text = f"{label} {soft} {hard} {unit}"
    if mode == "missing":
        text = "Limit Soft Limit Hard Limit Units"
    elif mode == "duplicate":
        text += "\n" + text
    elif mode == "malformed":
        text = label
    read_text.return_value = text
    if mode == "read_error":
        read_text.side_effect = OSError("limits unavailable")
    result = probe(probe_context)
    assert result.passed is (mode == "valid"), result.message
