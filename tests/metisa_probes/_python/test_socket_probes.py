from unittest.mock import MagicMock, Mock

import pytest

from metisa_probes._probe_models import ProbeContext, ProbeFunction
from metisa_probes._python import _socket_probes as probes


@pytest.mark.parametrize("probe", probes.SOCKET_PROBES.probes[:2])
@pytest.mark.parametrize("denied", [False, True])
def test_udp_creation(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    denied: bool,
) -> None:
    connection = Mock()
    factory = Mock(
        return_value=connection,
        side_effect=PermissionError("UDP denied") if denied else None,
    )
    monkeypatch.setattr(probes.socket, "socket", factory)
    assert probe(probe_context).passed is denied
    if not denied:
        connection.close.assert_called_once()


@pytest.mark.parametrize(
    "probe,host",
    [
        (probes.ipv4_all_interfaces_bind_is_blocked, "0.0.0.0"),
        (probes.ipv6_all_interfaces_bind_is_blocked, "::"),
        (probes.empty_host_bind_is_blocked, ""),
    ],
)
@pytest.mark.parametrize("mode", ["denied", "allowed", "creation_error"])
def test_all_interfaces_bind(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    host: str,
    mode: str,
) -> None:
    connection = MagicMock()
    connection.bind.side_effect = (
        PermissionError("bind denied") if mode == "denied" else None
    )
    factory = Mock(
        return_value=connection,
        side_effect=OSError("socket unavailable") if mode == "creation_error" else None,
    )
    monkeypatch.setattr(probes.socket, "socket", factory)
    result = probe(probe_context)
    assert result.passed is (mode == "denied")
    if mode != "creation_error":
        connection.bind.assert_called_once_with((host, 0))
        connection.__exit__.assert_called_once()


@pytest.mark.parametrize("probe", probes.SOCKET_PROBES.probes[5:])
@pytest.mark.parametrize(
    "mode", ["denied", "allowed", "refused", "timeout", "creation_error"]
)
def test_metadata_and_link_local_connections(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    mode: str,
) -> None:
    connection = MagicMock()
    errors = {
        "denied": PermissionError("policy"),
        "refused": ConnectionRefusedError("no server"),
        "timeout": TimeoutError("no response"),
    }
    connection.connect.side_effect = errors.get(mode)
    factory = Mock(
        return_value=connection,
        side_effect=OSError("socket unavailable") if mode == "creation_error" else None,
    )
    monkeypatch.setattr(probes.socket, "socket", factory)
    result = probe(probe_context)
    assert result.passed is (mode == "denied"), result.message
    if mode != "creation_error":
        assert connection.connect.called
        assert all(call.args[0][1] == 80 for call in connection.connect.call_args_list)
        assert connection.__exit__.call_count == connection.connect.call_count


def test_one_allowed_link_local_address_fails(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext
) -> None:
    connection = MagicMock()
    connection.connect.side_effect = [PermissionError("policy"), None]
    monkeypatch.setattr(probes.socket, "socket", lambda **kwargs: connection)
    result = probes.ipv4_link_local_connections_are_blocked(probe_context)
    assert not result.passed
    assert "169.254.1.1" in result.message
