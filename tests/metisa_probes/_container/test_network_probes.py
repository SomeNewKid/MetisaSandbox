import errno
import socket
import urllib.error
from collections.abc import Callable
from email.message import Message
from unittest.mock import MagicMock, Mock

import pytest

from metisa_common.specification_models import (
    Capability,
    HaproxyBackend,
    HaproxySpecification,
)
from metisa_probes._container import _network_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction

_NETWORK = frozenset({Capability.NETWORK})
_INTERNET = _NETWORK | {Capability.INTERNET}
_LOCALNET = _NETWORK | {Capability.LOCALNET}
_OTEL = _NETWORK | {Capability.OTEL_COLLECTOR}
_HAPROXY = HaproxySpecification(frozenset(), (HaproxyBackend(3306, "database", 3306),))


@pytest.mark.parametrize(
    "addresses,passed", [([], False), (["127.0.0.1"], False), (["172.18.0.2"], True)]
)
def test_workload_alias(
    monkeypatch: pytest.MonkeyPatch,
    context_with: Callable[..., ProbeContext],
    addresses: list[str],
    passed: bool,
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", (address, 0))
            for address in addresses
        ],
    )
    assert (
        probes.docker_network_alias_resolved(context_with(capabilities=_NETWORK)).passed
        is passed
    )


@pytest.mark.parametrize(
    "interfaces,passed",
    [([(1, "lo")], True), ([], False), ([(1, "lo"), (2, "eth0")], False)],
)
def test_network_disabled_interfaces(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    interfaces: list[tuple[int, str]],
    passed: bool,
) -> None:
    monkeypatch.setattr(socket, "if_nameindex", lambda: interfaces)
    assert probes.only_loopback_network_interface_exists(probe_context).passed is passed


@pytest.mark.parametrize(
    "enabled,endpoint,passed",
    [
        (False, None, True),
        (False, "0B00007F:8123", False),
        (True, "0B00007F:8123", True),
        (True, "0100007F:8123", False),
        (True, None, False),
        (True, "bad", False),
    ],
)
def test_tcp_listeners(
    read_text: Mock,
    context_with: Callable[..., ProbeContext],
    enabled: bool,
    endpoint: str | None,
    passed: bool,
) -> None:
    table = "header\n" + (f"0: {endpoint} 00000000:0000 0A\n" if endpoint else "")
    read_text.side_effect = [table, "header\n"]
    context = context_with(capabilities=_NETWORK if enabled else frozenset())
    assert (
        probes.docker_dns_resolver_is_only_listening_tcp_endpoint(context).passed
        is passed
    )


@pytest.mark.parametrize(
    "environment,discovered,passed",
    [
        ({}, {}, True),
        ({"HTTP_PROXY": ""}, {}, False),
        ({}, {"http": "http://proxy"}, False),
    ],
)
def test_absent_proxy_configuration(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    environment: dict[str, str],
    discovered: dict[str, str],
    passed: bool,
) -> None:
    monkeypatch.setattr(probes.os, "environ", environment)
    monkeypatch.setattr(probes.urllib.request, "getproxies", lambda: discovered)
    assert probes.proxy_configuration_is_absent(probe_context).passed is passed


@pytest.mark.parametrize(
    "schemes,passed",
    [
        ({}, False),
        ({"http": "proxy"}, False),
        ({"http": "proxy", "https": "proxy"}, True),
    ],
)
def test_required_proxy_configuration(
    monkeypatch: pytest.MonkeyPatch,
    context_with: Callable[..., ProbeContext],
    schemes: dict[str, str],
    passed: bool,
) -> None:
    monkeypatch.setattr(probes.urllib.request, "getproxies", lambda: schemes)
    assert (
        probes.proxy_configuration_exists(context_with(capabilities=_INTERNET)).passed
        is passed
    )


@pytest.mark.parametrize(
    "probe,policy",
    [
        (probes.external_http_is_blocked, "blocked"),
        (probes.external_https_is_blocked, "blocked"),
        (probes.external_http_is_allowed, "allowed"),
        (probes.external_https_is_allowed, "allowed"),
        (probes.disallowed_external_http_is_blocked, "proxy"),
        (probes.disallowed_external_https_is_blocked, "proxy"),
    ],
)
@pytest.mark.parametrize("response", [200, 209, 210, 403, 500, "offline"])
def test_http_policy_results(
    monkeypatch: pytest.MonkeyPatch,
    context_with: Callable[..., ProbeContext],
    probe: ProbeFunction,
    policy: str,
    response: int | str,
) -> None:
    reply = MagicMock(status=response)
    reply.__enter__.return_value = reply
    request = Mock(return_value=reply)
    if response == "offline":
        request.side_effect = urllib.error.URLError("offline")
    elif response in (403, 500):
        request.side_effect = urllib.error.HTTPError(
            "http://example.com", response, "error", Message(), None
        )
    monkeypatch.setattr(probes.urllib.request, "urlopen", request)
    context = context_with(
        capabilities=frozenset() if policy == "blocked" else _INTERNET
    )
    expected = (
        response == "offline"
        if policy == "blocked"
        else response in (200, 209)
        if policy == "allowed"
        else response == 403
    )
    result = probe(context)
    assert result.passed is expected, result.message
    request.assert_called_once()


def test_https_connect_proxy_denial(
    monkeypatch: pytest.MonkeyPatch, context_with: Callable[..., ProbeContext]
) -> None:
    request = Mock(
        side_effect=urllib.error.URLError("Tunnel connection failed: 403 Forbidden")
    )
    monkeypatch.setattr(probes.urllib.request, "urlopen", request)
    assert probes.disallowed_external_https_is_blocked(
        context_with(capabilities=_INTERNET)
    ).passed


@pytest.mark.parametrize(
    "probe",
    [
        probes.docker_network_alias_resolved,
        probes.docker_dns_resolution_works,
        probes.haproxy_alias_resolves,
        probes.haproxy_alias_is_absent,
        probes.haproxy_declared_listeners_are_reachable,
        probes.haproxy_declared_listeners_are_unavailable,
        probes.haproxy_undeclared_listener_is_unavailable,
        probes.haproxy_health_endpoint_is_private,
        probes.otel_collector_alias_resolves,
        probes.otel_collector_alias_is_absent,
        probes.otel_collector_listener_is_reachable,
        probes.otel_collector_listener_is_unavailable,
        probes.external_http_is_allowed,
        probes.external_https_is_allowed,
        probes.disallowed_external_http_is_blocked,
        probes.disallowed_external_https_is_blocked,
        probes.proxy_configuration_exists,
    ],
)
def test_disabled_capabilities_skip_without_io(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, probe: ProbeFunction
) -> None:
    unexpected = Mock(
        side_effect=AssertionError("disabled probe attempted network I/O")
    )
    monkeypatch.setattr(socket, "getaddrinfo", unexpected)
    monkeypatch.setattr(probes.urllib.request, "urlopen", unexpected)
    result = probe(probe_context)
    assert result.passed
    assert "Skipping" in result.message
    unexpected.assert_not_called()


@pytest.mark.parametrize(
    "mode", ["valid", "wrong_resolver", "unreachable", "no_addresses", "read_error"]
)
def test_docker_dns(
    monkeypatch: pytest.MonkeyPatch,
    read_text: Mock,
    context_with: Callable[..., ProbeContext],
    mode: str,
) -> None:
    read_text.return_value = (
        "nameserver 8.8.8.8" if mode == "wrong_resolver" else "nameserver 127.0.0.11"
    )
    if mode == "read_error":
        read_text.side_effect = OSError("cannot read resolver")
    monkeypatch.setattr(
        probes,
        "_tcp_connection_errors",
        lambda *args: [ConnectionRefusedError()] if mode == "unreachable" else [],
    )
    monkeypatch.setattr(
        probes,
        "_resolve_network_alias",
        lambda alias: set() if mode == "no_addresses" else {"172.18.0.2"},
    )
    assert probes.docker_dns_resolution_works(
        context_with(capabilities=_NETWORK)
    ).passed is (mode == "valid")


@pytest.mark.parametrize(
    "probe,capabilities",
    [
        (probes.haproxy_alias_resolves, _LOCALNET),
        (probes.otel_collector_alias_resolves, _OTEL),
    ],
)
@pytest.mark.parametrize("mode", ["valid", "empty", "invalid"])
def test_service_alias_resolution(
    monkeypatch: pytest.MonkeyPatch,
    context_with: Callable[..., ProbeContext],
    probe: ProbeFunction,
    capabilities: frozenset[Capability],
    mode: str,
) -> None:
    resolve = Mock(return_value={"172.18.0.2"} if mode == "valid" else set())
    if mode == "invalid":
        resolve.side_effect = ValueError("loopback address")
    monkeypatch.setattr(probes, "_resolve_network_alias", resolve)
    assert probe(context_with(capabilities=capabilities)).passed is (mode == "valid")


@pytest.mark.parametrize(
    "probe", [probes.haproxy_alias_is_absent, probes.otel_collector_alias_is_absent]
)
@pytest.mark.parametrize(
    "mode",
    [
        "absent",
        "present",
        "temporary_control_ok",
        "temporary_control_failed",
        "unexpected",
    ],
)
def test_hidden_service_dns(
    monkeypatch: pytest.MonkeyPatch,
    context_with: Callable[..., ProbeContext],
    probe: ProbeFunction,
    mode: str,
) -> None:
    lookup = Mock(return_value=[])
    if mode == "absent":
        lookup.side_effect = socket.gaierror(socket.EAI_NONAME, "absent")
    elif mode.startswith("temporary"):
        lookup.side_effect = socket.gaierror(socket.EAI_AGAIN, "try again")
    elif mode == "unexpected":
        lookup.side_effect = OSError("resolver broken")
    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    monkeypatch.setattr(
        probes,
        "_resolve_network_alias",
        lambda alias: set() if mode == "temporary_control_failed" else {"172.18.0.2"},
    )
    result = probe(context_with(capabilities=_NETWORK))
    assert result.passed is (mode in ("absent", "temporary_control_ok")), result.message


@pytest.mark.parametrize(
    "probe,capabilities",
    [
        (probes.haproxy_declared_listeners_are_reachable, _LOCALNET),
        (probes.otel_collector_listener_is_reachable, _OTEL),
        (
            probes.haproxy_declared_listeners_are_unavailable,
            _LOCALNET | {Capability.MCP_SERVER},
        ),
        (probes.otel_collector_listener_is_unavailable, _NETWORK),
        (probes.haproxy_undeclared_listener_is_unavailable, _LOCALNET),
        (probes.haproxy_health_endpoint_is_private, _LOCALNET),
    ],
)
@pytest.mark.parametrize(
    "mode", ["connected", "refused", "timeout", "unexpected", "lookup_error"]
)
def test_service_listener_policy(
    monkeypatch: pytest.MonkeyPatch,
    context_with: Callable[..., ProbeContext],
    probe: ProbeFunction,
    capabilities: frozenset[Capability],
    mode: str,
) -> None:
    outcomes = {
        "connected": [],
        "refused": [ConnectionRefusedError(errno.ECONNREFUSED, "refused")],
        "timeout": [TimeoutError("timeout")],
        "unexpected": [OSError(errno.EIO, "I/O error")],
    }
    connect = Mock(return_value=outcomes.get(mode))
    if mode == "lookup_error":
        connect.side_effect = OSError("lookup failed")
    monkeypatch.setattr(probes, "_tcp_connection_errors", connect)
    context = context_with(capabilities=capabilities, haproxy=_HAPROXY)
    requires_refusal = probe in (
        probes.haproxy_undeclared_listener_is_unavailable,
        probes.haproxy_health_endpoint_is_private,
    )
    requires_connection = probe in (
        probes.haproxy_declared_listeners_are_reachable,
        probes.otel_collector_listener_is_reachable,
    )
    expected = (
        mode == "connected"
        if requires_connection
        else mode == "refused"
        if requires_refusal
        else mode in ("refused", "timeout")
    )
    result = probe(context)
    assert result.passed is expected, result.message


@pytest.mark.parametrize(
    "mode",
    [
        "empty",
        "ipv4_default",
        "ipv6_default",
        "reject_sentinel",
        "malformed",
        "read_error",
    ],
)
def test_default_routes(
    read_text: Mock, probe_context: ProbeContext, mode: str
) -> None:
    ipv4 = "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n"
    ipv6 = ""
    if mode == "ipv4_default":
        ipv4 += "eth0 00000000 010012AC 0003 0 0 0 00000000 0 0 0\n"
    elif mode in ("ipv6_default", "reject_sentinel"):
        flags = "00000001" if mode == "ipv6_default" else "00000201"
        ipv6 = f"{'0' * 32} 00 {'0' * 32} 00 {'0' * 32} 0 0 0 {flags} lo\n"
    elif mode == "malformed":
        ipv4 += "invalid route"
    read_text.side_effect = (
        OSError("route unavailable") if mode == "read_error" else [ipv4, ipv6]
    )
    result = probes.workload_has_no_default_route(probe_context)
    assert result.passed is (mode in ("empty", "reject_sentinel")), result.message


@pytest.mark.parametrize("address", ["127.0.0.1", "::1", "0.0.0.0", "::"])
def test_alias_helper_rejects_local_or_unspecified(
    monkeypatch: pytest.MonkeyPatch, address: str
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", (address, 80))
        ],
    )
    with pytest.raises(ValueError, match="loopback or unspecified"):
        probes._resolve_network_alias("service")


def test_tcp_helper_tries_all_addresses_and_stops_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    addresses = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("172.18.0.2", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("172.18.0.3", 80)),
    ]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: addresses)
    first, second = MagicMock(), MagicMock()
    first.__enter__.return_value = first
    second.__enter__.return_value = second
    first.connect.side_effect = ConnectionRefusedError(errno.ECONNREFUSED, "refused")
    factory = Mock(side_effect=[first, second])
    monkeypatch.setattr(socket, "socket", factory)
    assert probes._tcp_connection_errors("service", 80) == []
    assert factory.call_count == 2
    first.__exit__.assert_called_once()
    second.__exit__.assert_called_once()
