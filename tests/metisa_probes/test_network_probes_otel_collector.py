from __future__ import annotations

import errno
import socket
from dataclasses import replace
from unittest.mock import Mock

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import Capability
from metisa_probes._container import _network_probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction

_PRESENCE_PROBES = (
    _network_probes.otel_collector_alias_resolves,
    _network_probes.otel_collector_listener_is_reachable,
)
_ABSENCE_PROBES = (
    _network_probes.otel_collector_alias_is_absent,
    _network_probes.otel_collector_listener_is_unavailable,
)


@pytest.mark.parametrize("probe", _PRESENCE_PROBES + _ABSENCE_PROBES)
@pytest.mark.parametrize("collector_enabled", [False, True])
def test_no_network_skips_without_io(
    monkeypatch: pytest.MonkeyPatch,
    probe: ProbeFunction,
    collector_enabled: bool,
) -> None:
    lookup = Mock(side_effect=AssertionError("Unexpected DNS lookup"))
    connection = Mock(side_effect=AssertionError("Unexpected TCP connection"))
    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    monkeypatch.setattr(_network_probes, "_tcp_connection_errors", connection)
    capabilities = {Capability.OTEL_COLLECTOR} if collector_enabled else set()

    result = probe(_context(capabilities))

    assert result.passed
    assert "Skipping probe" in result.message
    lookup.assert_not_called()
    connection.assert_not_called()


@pytest.mark.parametrize(
    ("probe", "collector_enabled"),
    [(probe, False) for probe in _PRESENCE_PROBES]
    + [(probe, True) for probe in _ABSENCE_PROBES],
)
def test_inapplicable_capability_skips_without_io(
    monkeypatch: pytest.MonkeyPatch,
    probe: ProbeFunction,
    collector_enabled: bool,
) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", Mock(side_effect=AssertionError("Unexpected lookup"))
    )
    monkeypatch.setattr(
        _network_probes,
        "_tcp_connection_errors",
        Mock(side_effect=AssertionError("Unexpected connection")),
    )
    capabilities = {Capability.NETWORK}
    if collector_enabled:
        capabilities.add(Capability.OTEL_COLLECTOR)

    result = probe(_context(capabilities))

    assert result.passed
    assert "Skipping probe" in result.message


@pytest.mark.parametrize(
    ("address", "passed"),
    [("172.20.0.2", True), ("127.0.0.1", False), ("0.0.0.0", False)],
)
def test_alias_requires_non_loopback_address(
    monkeypatch: pytest.MonkeyPatch, address: str, passed: bool
) -> None:
    addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]
    monkeypatch.setattr(socket, "getaddrinfo", Mock(return_value=addresses))

    result = _network_probes.otel_collector_alias_resolves(
        _context({Capability.NETWORK, Capability.OTEL_COLLECTOR})
    )

    assert result.passed is passed


@pytest.mark.parametrize("probe", _ABSENCE_PROBES)
@pytest.mark.parametrize(
    ("dns_error", "control_addresses", "passed"),
    [
        (socket.EAI_NONAME, {"172.20.0.3"}, True),
        (socket.EAI_AGAIN, {"172.20.0.3"}, True),
        (socket.EAI_AGAIN, set(), False),
        (socket.EAI_AGAIN, OSError("DNS unavailable"), False),
        (socket.EAI_FAIL, {"172.20.0.3"}, False),
    ],
)
def test_absence_distinguishes_missing_alias_from_dns_failure(
    monkeypatch: pytest.MonkeyPatch,
    probe: ProbeFunction,
    dns_error: int,
    control_addresses: set[str] | OSError,
    passed: bool,
) -> None:
    lookup = Mock(side_effect=socket.gaierror(dns_error, "DNS lookup failed"))
    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    control = Mock(return_value=control_addresses)
    if isinstance(control_addresses, OSError):
        control.side_effect = control_addresses
    monkeypatch.setattr(_network_probes, "_resolve_network_alias", control)

    result = probe(_context({Capability.NETWORK}))

    assert result.passed is passed
    if dns_error == socket.EAI_AGAIN:
        control.assert_called_once_with("metisa-workload")
    else:
        control.assert_not_called()


def test_absence_rejects_a_resolvable_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.20.0.2", 0))]
    monkeypatch.setattr(socket, "getaddrinfo", Mock(return_value=addresses))

    result = _network_probes.otel_collector_alias_is_absent(
        _context({Capability.NETWORK})
    )

    assert not result.passed


@pytest.mark.parametrize(
    ("errors", "reachable", "unavailable"),
    [
        ([], True, False),
        ([ConnectionRefusedError(errno.ECONNREFUSED, "Refused")], False, True),
        ([TimeoutError("Timed out")], False, True),
        ([OSError(errno.ENETUNREACH, "Unreachable")], False, True),
        ([OSError(errno.EIO, "Unexpected I/O failure")], False, False),
    ],
)
def test_listener_checks_the_otlp_port(
    monkeypatch: pytest.MonkeyPatch,
    errors: list[OSError],
    reachable: bool,
    unavailable: bool,
) -> None:
    connection = Mock(return_value=errors)
    monkeypatch.setattr(_network_probes, "_tcp_connection_errors", connection)

    presence = _network_probes.otel_collector_listener_is_reachable(
        _context({Capability.NETWORK, Capability.OTEL_COLLECTOR})
    )
    absence = _network_probes.otel_collector_listener_is_unavailable(
        _context({Capability.NETWORK})
    )

    assert presence.passed is reachable
    assert absence.passed is unavailable
    assert connection.call_count == 2
    connection.assert_called_with("metisa-otel-collector", 4318)


def test_collector_probes_are_registered() -> None:
    for probe in _PRESENCE_PROBES + _ABSENCE_PROBES:
        assert probe in _network_probes.NETWORK_PROBES.probes


def _context(capabilities: set[Capability]) -> ProbeContext:
    specification = parse_specification('agent_name = "probe_test"')
    specification = replace(specification, capabilities=frozenset(capabilities))
    return ProbeContext(specification)
