import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from metisa_probes._container import _docker_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction


@pytest.mark.parametrize(
    "probe", [probes.docker_socket_is_absent, probes.docker_host_paths_are_absent]
)
@pytest.mark.parametrize("present", [False, True])
def test_host_paths(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    present: bool,
) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: present)
    assert probe(probe_context).passed is not present


@pytest.mark.parametrize(
    "text,passed",
    [
        ("0::/\n", True),
        ("2:cpu:/\n0::/", True),
        ("0::/docker/host-id", False),
        ("malformed", False),
        ("", False),
    ],
)
def test_private_cgroup_namespace(
    read_text: Mock, probe_context: ProbeContext, text: str, passed: bool
) -> None:
    read_text.return_value = text
    assert probes.cgroup_namespace_is_private(probe_context).passed is passed


@pytest.mark.parametrize(
    "name,passed", [("docker-init\n", True), ("python", False), ("", False)]
)
def test_init_process(
    read_text: Mock, probe_context: ProbeContext, name: str, passed: bool
) -> None:
    read_text.return_value = name
    assert probes.init_process_is_enabled(probe_context).passed is passed


@pytest.mark.parametrize(
    "evidence", ["none", "dockerenv", "cgroup", "mountinfo", "hostname"]
)
def test_runtime_evidence(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, evidence: str
) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: evidence == "dockerenv")

    def read(self: Path, **kwargs: object) -> str:
        if evidence == "cgroup" and self.name == "cgroup":
            return "0::/docker/id"
        if evidence == "mountinfo" and self.name == "mountinfo":
            return "containerd"
        return ""

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(
        probes.socket,
        "gethostname",
        lambda: "abcdef123456" if evidence == "hostname" else "ordinary-host",
    )
    assert probes.docker_container_runtime_is_detected(probe_context).passed is (
        evidence != "none"
    )


@pytest.mark.parametrize(
    "probe,variable",
    [
        (probes.ssh_agent_is_unavailable, "SSH_AUTH_SOCK"),
        (probes.gpg_agent_is_unavailable, "GPG_AGENT_INFO"),
    ],
)
@pytest.mark.parametrize("present", [False, True])
def test_agent_environment(
    monkeypatch: pytest.MonkeyPatch,
    read_text: Mock,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    variable: str,
    present: bool,
) -> None:
    monkeypatch.setattr(probes.os, "environ", {variable: ""} if present else {})
    read_text.return_value = "Num RefCount Protocol Flags Type St Inode Path\n"
    assert probe(probe_context).passed is not present


def test_gpg_socket_without_environment(
    monkeypatch: pytest.MonkeyPatch, read_text: Mock, probe_context: ProbeContext
) -> None:
    monkeypatch.setattr(probes.os, "environ", {})
    read_text.return_value = "0000: 2 0 0 1 1 123 /run/user/1000/gnupg/S.gpg-agent"
    assert not probes.gpg_agent_is_unavailable(probe_context).passed


@pytest.mark.parametrize("mode", ["directory", "socket", "malformed", "stat_error"])
def test_socket_mounts(
    monkeypatch: pytest.MonkeyPatch,
    read_text: Mock,
    probe_context: ProbeContext,
    mode: str,
) -> None:
    read_text.return_value = (
        "bad"
        if mode == "malformed"
        else "1 0 0:1 / /run/host\\040socket rw - tmpfs tmpfs rw"
    )
    metadata = Mock(
        return_value=SimpleNamespace(
            st_mode=stat.S_IFSOCK if mode == "socket" else stat.S_IFDIR
        )
    )
    if mode == "stat_error":
        metadata.side_effect = OSError("cannot inspect mount")
    monkeypatch.setattr(Path, "stat", metadata)
    assert probes.host_socket_mounts_are_absent(probe_context).passed is (
        mode == "directory"
    )


@pytest.mark.parametrize(
    "probe",
    [
        probes.cgroup_namespace_is_private,
        probes.init_process_is_enabled,
        probes.host_socket_mounts_are_absent,
        probes.gpg_agent_is_unavailable,
    ],
)
def test_required_metadata_unreadable(
    monkeypatch: pytest.MonkeyPatch,
    read_text: Mock,
    probe_context: ProbeContext,
    probe: ProbeFunction,
) -> None:
    monkeypatch.setattr(probes.os, "environ", {})
    read_text.side_effect = OSError("metadata unavailable")
    assert not probe(probe_context).passed
