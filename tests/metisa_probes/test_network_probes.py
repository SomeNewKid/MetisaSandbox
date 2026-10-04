"""Tests for the additional Docker DNS and HAProxy isolation probes."""

from __future__ import annotations

import errno
import socket
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import (
    Capability,
    HaproxyBackend,
    HaproxySpecification,
)
from metisa_probes.container import network_probes as probes
from metisa_probes.probe_models import ProbeContext, ProbeFunction


@pytest.fixture
def context() -> ProbeContext:
    """Build a localnet-enabled context without contacting Docker."""
    specification = parse_specification('agent_name = "sample_agent"')
    specification = replace(
        specification,
        capabilities=frozenset({Capability.NETWORK, Capability.LOCALNET}),
        haproxy=HaproxySpecification(
            backends=(HaproxyBackend(3306, "host.docker.internal", 3306),),
        ),
    )
    return ProbeContext(specification=specification)


@pytest.mark.parametrize(
    "probe",
    [
        probes.haproxy_alias_resolves,
        probes.haproxy_declared_listeners_are_reachable,
        probes.haproxy_undeclared_listener_is_unavailable,
        probes.haproxy_health_endpoint_is_private,
        probes.direct_backend_access_is_blocked,
    ],
)
def test_localnet_probes_skip_without_capability(
    context: ProbeContext, probe: ProbeFunction
) -> None:
    """Skip localnet checks when the capability is absent."""
    specification = replace(context.specification, capabilities=frozenset())
    result = probe(ProbeContext(specification))
    assert result.passed
    assert "Skipping" in result.message


@pytest.mark.parametrize(
    "code, expected", [(socket.EAI_NONAME, True), (socket.EAI_AGAIN, False)]
)
def test_absent_alias_requires_name_not_found(
    context: ProbeContext, monkeypatch: pytest.MonkeyPatch, code: int, expected: bool
) -> None:
    """Distinguish missing aliases from transient DNS failures."""
    context = ProbeContext(
        replace(context.specification, capabilities=frozenset({Capability.NETWORK}))
    )
    monkeypatch.setattr(
        socket, "getaddrinfo", Mock(side_effect=socket.gaierror(code, "lookup failed"))
    )
    assert probes.haproxy_alias_is_absent(context).passed is expected


def test_absent_alias_fails_when_present(
    context: ProbeContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject an HAProxy alias when localnet is disabled."""
    context = ProbeContext(
        replace(context.specification, capabilities=frozenset({Capability.NETWORK}))
    )
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        Mock(
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.20.0.2", 0))
            ]
        ),
    )
    assert not probes.haproxy_alias_is_absent(context).passed


@pytest.mark.parametrize(
    "address, expected",
    [("172.20.0.2", True), ("127.0.0.2", False), ("::1", False), ("0.0.0.0", False)],
)
def test_alias_rejects_loopback_and_unspecified_addresses(
    context: ProbeContext, monkeypatch: pytest.MonkeyPatch, address: str, expected: bool
) -> None:
    """Require meaningful non-loopback HAProxy addresses."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        Mock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]),
    )
    assert probes.haproxy_alias_resolves(context).passed is expected


@pytest.mark.parametrize(
    "error, expected",
    [
        (ConnectionRefusedError(errno.ECONNREFUSED, "refused"), True),
        (TimeoutError(), False),
        (PermissionError(), False),
        (None, False),
    ],
)
def test_private_health_requires_refusal(
    context: ProbeContext,
    monkeypatch: pytest.MonkeyPatch,
    error: OSError | None,
    expected: bool,
) -> None:
    """Require an explicit refusal rather than an inconclusive failure."""
    connect = Mock(return_value=[] if error is None else [error])
    monkeypatch.setattr(probes, "_tcp_connection_errors", connect)
    assert probes.haproxy_health_endpoint_is_private(context).passed is expected
    connect.assert_called_once_with("metisa-haproxy", 8404)


def test_health_port_conflict_fails(context: ProbeContext) -> None:
    """Reject backend listeners that collide with the health endpoint."""
    haproxy = HaproxySpecification(
        (HaproxyBackend(8404, "host.docker.internal", 3306),)
    )
    context = ProbeContext(replace(context.specification, haproxy=haproxy))
    assert not probes.haproxy_health_endpoint_is_private(context).passed


def test_undeclared_probe_chooses_only_one_unused_port(
    context: ProbeContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Choose a single undeclared port without scanning the sidecar."""
    haproxy = HaproxySpecification(
        (HaproxyBackend(65535, "host.docker.internal", 3306),)
    )
    context = ProbeContext(replace(context.specification, haproxy=haproxy))
    connect = Mock(return_value=[ConnectionRefusedError(errno.ECONNREFUSED, "refused")])
    monkeypatch.setattr(probes, "_tcp_connection_errors", connect)
    assert probes.haproxy_undeclared_listener_is_unavailable(context).passed
    connect.assert_called_once_with("metisa-haproxy", 65534)


@pytest.mark.parametrize(
    "errors, expected",
    [
        ([], False),
        ([TimeoutError()], True),
        ([OSError(errno.ENETUNREACH, "unreachable")], True),
        ([ConnectionRefusedError(errno.ECONNREFUSED, "refused")], False),
        ([PermissionError()], False),
    ],
)
def test_direct_backend_distinguishes_isolation_from_other_failures(
    context: ProbeContext,
    monkeypatch: pytest.MonkeyPatch,
    errors: list[OSError],
    expected: bool,
) -> None:
    """Do not interpret reachable stacks or Python guards as isolation."""
    monkeypatch.setattr(probes, "_tcp_connection_errors", Mock(return_value=errors))
    assert probes.direct_backend_access_is_blocked(context).passed is expected


def test_direct_backend_dns_error_fails(
    context: ProbeContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Do not treat unresolved backend names as evidence of isolation."""
    monkeypatch.setattr(
        probes,
        "_tcp_connection_errors",
        Mock(side_effect=socket.gaierror(socket.EAI_NONAME, "missing")),
    )
    assert not probes.direct_backend_access_is_blocked(context).passed


def test_declared_probe_checks_every_listener(
    context: ProbeContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail if any declared listener cannot accept connections."""
    haproxy = HaproxySpecification(
        (
            HaproxyBackend(3306, "host.docker.internal", 3306),
            HaproxyBackend(1521, "172.16.1.2", 1521),
        )
    )
    context = ProbeContext(replace(context.specification, haproxy=haproxy))
    connect = Mock(side_effect=[[], [TimeoutError()]])
    monkeypatch.setattr(probes, "_tcp_connection_errors", connect)
    assert not probes.haproxy_declared_listeners_are_reachable(context).passed
    assert connect.call_count == 2


@pytest.mark.parametrize(
    "resolver, reachable, expected",
    [
        ("127.0.0.11", True, True),
        ("8.8.8.8", True, False),
        ("127.0.0.11", False, False),
    ],
)
def test_docker_dns_verification(
    context: ProbeContext,
    monkeypatch: pytest.MonkeyPatch,
    resolver: str,
    reachable: bool,
    expected: bool,
) -> None:
    """Check resolver configuration, TCP availability, and alias resolution."""
    monkeypatch.setattr(
        Path, "read_text", Mock(return_value=f"nameserver {resolver}\n")
    )
    monkeypatch.setattr(
        probes,
        "_tcp_connection_errors",
        Mock(return_value=[] if reachable else [TimeoutError()]),
    )
    monkeypatch.setattr(
        probes, "_resolve_network_alias", Mock(return_value={"172.20.0.3"})
    )
    assert probes.docker_dns_resolution_works(context).passed is expected


@pytest.mark.parametrize(
    "ipv4, ipv6, expected",
    [
        ("", "", True),
        ("eth0 00000000 010014AC 0003 0 0 0 00000000 0 0 0\n", "", False),
        ("", "0 00 0 00 0 00000000 00000000 00000000 00000001 eth0\n", False),
        ("", "0 00 0 00 0 FFFFFFFF 00000001 00000000 00200200 lo\n", True),
        ("malformed\n", "", False),
        ("", "malformed\n", False),
    ],
)
def test_route_probe_checks_both_families_and_ignores_reject_sentinel(
    context: ProbeContext,
    monkeypatch: pytest.MonkeyPatch,
    ipv4: str,
    ipv6: str,
    expected: bool,
) -> None:
    """Reject usable default routes and malformed route entries."""
    monkeypatch.setattr(
        Path,
        "read_text",
        Mock(
            side_effect=[
                "Iface Destination Gateway Flags RefCnt Use Metric "
                "Mask MTU Window IRTT\n" + ipv4,
                ipv6,
            ]
        ),
    )
    assert probes.workload_has_no_default_route(context).passed is expected


def test_tcp_helper_checks_all_addresses_and_closes_sockets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Try alternate addresses with timeouts and close each socket."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        Mock(
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.20.0.2", 3306)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.20.0.3", 3306)),
            ]
        ),
    )
    first = Mock()
    first.connect.side_effect = TimeoutError()
    second = Mock()
    first_manager = Mock(
        __enter__=Mock(return_value=first), __exit__=Mock(return_value=False)
    )
    second_manager = Mock(
        __enter__=Mock(return_value=second), __exit__=Mock(return_value=False)
    )
    factory = Mock(side_effect=[first_manager, second_manager])
    monkeypatch.setattr(socket, "socket", factory)
    assert probes._tcp_connection_errors("metisa-haproxy", 3306) == []
    assert factory.call_count == 2
    first.settimeout.assert_called_once_with(3)
    second.settimeout.assert_called_once_with(3)
    first_manager.__exit__.assert_called_once()
    second_manager.__exit__.assert_called_once()
