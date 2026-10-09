"""Probes related to the Docker network."""

from __future__ import annotations

import errno
import ipaddress
import os
import socket
import ssl
import urllib.error
import urllib.request
from pathlib import Path

from metisa_common.specification_models import Capability

from ..probe_models import ProbeContext, ProbeGroup, ProbeResult

_WORKLOAD_NETWORK_ALIAS = "metisa-workload"
_DOCKER_DNS_RESOLVER = "127.0.0.11"
_HAPROXY_NETWORK_ALIAS = "metisa-haproxy"
_HAPROXY_HEALTH_PORT = 8404
_TCP_TIMEOUT_SECONDS = 3
_PROXY_ENVIRONMENT_VARIABLES = frozenset(
    {
        "all_proxy",
        "ftp_proxy",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    }
)


def docker_network_alias_resolved(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure the workload's Docker network alias resolves."""
    probe_name = "container__network__docker_network_alias_resolved"
    specification = probe_context.specification

    if Capability.NETWORK not in specification.capabilities:
        skipping = "Networking is not enabled. Skipping probe."
        return ProbeResult.success(probe_name, skipping)

    try:
        address_info = socket.getaddrinfo(
            _WORKLOAD_NETWORK_ALIAS,
            None,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as error:
        message = (
            f"Could not result Docker network alias {_WORKLOAD_NETWORK_ALIAS}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    addresses = sorted(
        {str(address[4][0]) for address in address_info if address[4][0] != "127.0.0.1"}
    )

    if not addresses:
        message = (
            f"Docker network alias {_WORKLOAD_NETWORK_ALIAS} "
            "did not resolve to a non-loopback IPv4 address."
        )
        return ProbeResult.failure(probe_name, message)

    resolution = ", ".join(addresses)
    message = f"Docker network alias {_WORKLOAD_NETWORK_ALIAS} resolved to {resolution}"
    return ProbeResult.success(probe_name, message)


def only_loopback_network_interface_exists(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure a network-disabled workload has only the loopback interface."""
    probe_name = "container__network__only_loopback_network_interface_exists"
    specification = probe_context.specification

    if Capability.NETWORK in specification.capabilities:
        message = "Networking is enabled. Skipping probe."
        return ProbeResult.success(probe_name, message)

    try:
        interface_names = {
            interface_name for _, interface_name in socket.if_nameindex()
        }
    except OSError as error:
        message = (
            f"Could not enumerate network interfaces: {type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    unexpected_interfaces = sorted(interface_names - {"lo"})

    if unexpected_interfaces:
        interfaces = ", ".join(unexpected_interfaces)
        message = f"Unexpected network interfaces found: {interfaces}"
        return ProbeResult.failure(probe_name, message)

    if "lo" not in interface_names:
        message = "The loopback network interface was not found."
        return ProbeResult.failure(probe_name, message)

    return ProbeResult.success(
        probe_name,
        "Only the loopback network interface exists.",
    )


def docker_dns_resolver_is_only_listening_tcp_endpoint(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure only Docker DNS listens when workload networking is enabled."""
    probe_name = (
        "container__network__docker_dns_resolver_is_only_listening_tcp_endpoint"
    )
    socket_table_paths = (
        Path("/proc/net/tcp"),
        Path("/proc/net/tcp6"),
    )
    listening_endpoints: list[tuple[str, str]] = []

    for socket_table_path in socket_table_paths:
        try:
            socket_table = socket_table_path.read_text(encoding="utf-8")
        except OSError as error:
            message = (
                f"Could not read {socket_table_path}: {type(error).__name__}: {error}"
            )
            return ProbeResult.failure(probe_name, message)

        for entry in socket_table.splitlines()[1:]:
            fields = entry.split()

            if len(fields) < 4:
                message = f"Malformed socket entry in {socket_table_path}: {entry!r}."
                return ProbeResult.failure(probe_name, message)

            if fields[3] == "0A":
                listening_endpoints.append((socket_table_path.name, fields[1]))

    specification = probe_context.specification

    if Capability.NETWORK not in specification.capabilities:
        if listening_endpoints:
            endpoints = _format_listening_endpoints(listening_endpoints)
            message = f"Unexpected listening TCP endpoints found: {endpoints}."
            return ProbeResult.failure(probe_name, message)

        message = "No TCP endpoints are listening while networking is disabled."
        return ProbeResult.success(probe_name, message)

    if len(listening_endpoints) != 1:
        endpoints = _format_listening_endpoints(listening_endpoints)
        message = (
            "Expected one Docker DNS TCP listener at "
            f"{_DOCKER_DNS_RESOLVER}, but found: {endpoints}."
        )
        return ProbeResult.failure(probe_name, message)

    socket_table_name, encoded_endpoint = listening_endpoints[0]

    if socket_table_name != "tcp":
        message = f"Unexpected IPv6 TCP listener found: {encoded_endpoint}."
        return ProbeResult.failure(probe_name, message)

    try:
        host, port = _decode_ipv4_proc_endpoint(encoded_endpoint)
    except ValueError as error:
        message = f"Could not decode TCP endpoint {encoded_endpoint!r}: {error}"
        return ProbeResult.failure(probe_name, message)

    if host != _DOCKER_DNS_RESOLVER:
        message = f"Unexpected listening TCP endpoint found: {host}:{port}."
        return ProbeResult.failure(probe_name, message)

    message = f"Docker DNS is the only listening TCP endpoint: {host}:{port}."
    return ProbeResult.success(probe_name, message)


def proxy_configuration_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure the workload receives no proxy configuration."""
    probe_name = "container__network__proxy_configuration_is_absent"
    specification = probe_context.specification

    if Capability.INTERNET in specification.capabilities:
        message = "Internet access is enabled. Skipping probe."
        return ProbeResult.success(probe_name, message)

    configured_variables = {
        variable_name: variable_value
        for variable_name, variable_value in os.environ.items()
        if variable_name.lower() in _PROXY_ENVIRONMENT_VARIABLES
    }

    if configured_variables:
        variables = ", ".join(
            f"{name}={value!r}" for name, value in sorted(configured_variables.items())
        )
        message = f"Proxy environment variables found: {variables}."
        return ProbeResult.failure(probe_name, message)

    discovered_proxies = urllib.request.getproxies()

    if discovered_proxies:
        proxies = ", ".join(
            f"{scheme}={value!r}"
            for scheme, value in sorted(discovered_proxies.items())
        )
        message = f"Python discovered proxy configuration: {proxies}."
        return ProbeResult.failure(probe_name, message)

    message = "No proxy configuration was found."
    return ProbeResult.success(probe_name, message)


def proxy_configuration_exists(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure an internet-enabled workload receives proxy configuration."""
    probe_name = "container__network__proxy_configuration_exists"
    specification = probe_context.specification

    if Capability.INTERNET not in specification.capabilities:
        message = "Internet access is not enabled. Skipping probe."
        return ProbeResult.success(probe_name, message)

    discovered_proxies = urllib.request.getproxies()
    required_schemes = {"http", "https"}
    missing_schemes = sorted(required_schemes - discovered_proxies.keys())

    if missing_schemes:
        schemes = ", ".join(missing_schemes)
        message = f"Proxy configuration is missing for: {schemes}."
        return ProbeResult.failure(probe_name, message)

    proxies = ", ".join(
        f"{scheme}={discovered_proxies[scheme]!r}"
        for scheme in sorted(required_schemes)
    )
    message = f"Python discovered proxy configuration: {proxies}."
    return ProbeResult.success(probe_name, message)


def external_http_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure outbound unsecured HTTP access is unavailable."""
    probe_name = "container__docker__external_http_is_blocked"
    specification = probe_context.specification

    if Capability.INTERNET in specification.capabilities:
        message = "Internet access is enabled. Skipping probe."
        return ProbeResult.success(probe_name, message)

    target_url = "http://example.com"
    timeout_seconds = 5

    request = urllib.request.Request(
        target_url,
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            status_code = response.status
    except urllib.error.HTTPError as error:
        # HTTPError means a remote HTTP server returned a response, so
        # outbound network access succeeded.
        message = (
            f"External HTTP request reached {target_url} "
            f"and returned HTTP {error.code}."
        )
        return ProbeResult.failure(probe_name, message)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        message = (
            f"External HTTP request to {target_url} was blocked: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.success(probe_name, message)

    message = (
        f"External HTTP request reached {target_url} and returned HTTP {status_code}."
    )
    return ProbeResult.failure(probe_name, message)


def external_http_is_allowed(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure an internet-enabled workload can access external HTTP."""
    probe_name = "container__network__external_http_is_allowed"
    specification = probe_context.specification

    if Capability.INTERNET not in specification.capabilities:
        message = "Internet access is not enabled. Skipping probe."
        return ProbeResult.success(probe_name, message)

    target_url = "http://example.com"
    timeout_seconds = 5
    request = urllib.request.Request(target_url, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.status
    except urllib.error.HTTPError as error:
        message = (
            f"External HTTP request reached {target_url} "
            f"and returned HTTP {error.code}."
        )
        return ProbeResult.failure(probe_name, message)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        message = (
            f"External HTTP request to {target_url} failed: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    if not 200 <= status_code <= 209:
        message = (
            f"External HTTP request reached {target_url} "
            f"and returned unexpected HTTP {status_code}."
        )
        return ProbeResult.failure(probe_name, message)

    message = (
        f"External HTTP request reached {target_url} and returned HTTP {status_code}."
    )
    return ProbeResult.success(probe_name, message)


def disallowed_external_http_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure the internet proxy denies HTTP to a disallowed destination."""
    probe_name = "container__network__disallowed_external_http_is_blocked"
    specification = probe_context.specification

    if Capability.INTERNET not in specification.capabilities:
        message = "Internet access is not enabled. Skipping probe."
        return ProbeResult.success(probe_name, message)

    target_url = "http://example.invalid"
    timeout_seconds = 5
    request = urllib.request.Request(target_url, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.status
    except urllib.error.HTTPError as error:
        if error.code == 403:
            message = f"External HTTP request to {target_url} was denied by the proxy."
            return ProbeResult.success(probe_name, message)

        message = (
            f"External HTTP request to {target_url} returned unexpected "
            f"HTTP {error.code}."
        )
        return ProbeResult.failure(probe_name, message)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        message = (
            f"Could not confirm proxy denial for {target_url}: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    message = (
        f"External HTTP request reached {target_url} and returned HTTP {status_code}."
    )
    return ProbeResult.failure(probe_name, message)


def external_https_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure outbound HTTPS access is unavailable."""
    probe_name = "container__network__external_https_is_blocked"
    specification = probe_context.specification

    if Capability.INTERNET in specification.capabilities:
        message = "Internet access is enabled. Skipping probe."
        return ProbeResult.success(probe_name, message)

    target_url = "https://example.com"
    timeout_seconds = 15

    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.check_hostname = False
    tls_context.verify_mode = ssl.CERT_NONE

    request = urllib.request.Request(target_url, method="GET")

    try:
        with urllib.request.urlopen(
            request, timeout=timeout_seconds, context=tls_context
        ) as response:
            status_code = response.status
    except urllib.error.HTTPError as error:
        # HTTPError means a remote HTTP server returned a response, so
        # outbound network access succeeded.
        message = (
            f"External HTTPS request reached {target_url} "
            f"and returned HTTP {error.code}."
        )
        return ProbeResult.failure(probe_name, message)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        message = (
            f"External HTTPS request to {target_url} was blocked: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.success(probe_name, message)

    message = (
        f"External HTTPS request reached {target_url} and returned HTTP {status_code}."
    )
    return ProbeResult.failure(probe_name, message)


def external_https_is_allowed(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure an internet-enabled workload can access external HTTPS."""
    probe_name = "container__network__external_https_is_allowed"
    specification = probe_context.specification

    if Capability.INTERNET not in specification.capabilities:
        message = "Internet access is not enabled. Skipping probe."
        return ProbeResult.success(probe_name, message)

    target_url = "https://example.com"
    timeout_seconds = 15

    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.check_hostname = False
    tls_context.verify_mode = ssl.CERT_NONE

    request = urllib.request.Request(target_url, method="GET")

    try:
        with urllib.request.urlopen(
            request, timeout=timeout_seconds, context=tls_context
        ) as response:
            status_code = response.status
    except urllib.error.HTTPError as error:
        message = (
            f"External HTTPS request reached {target_url} "
            f"and returned HTTP {error.code}."
        )
        return ProbeResult.failure(probe_name, message)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        message = (
            f"External HTTPS request to {target_url} failed: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    if not 200 <= status_code <= 209:
        message = (
            f"External HTTPS request reached {target_url} "
            f"and returned unexpected HTTP {status_code}."
        )
        return ProbeResult.failure(probe_name, message)

    message = (
        f"External HTTPS request reached {target_url} and returned HTTP {status_code}."
    )
    return ProbeResult.success(probe_name, message)


def disallowed_external_https_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure the internet proxy denies HTTPS to a disallowed destination."""
    probe_name = "container__network__disallowed_external_https_is_blocked"
    specification = probe_context.specification

    if Capability.INTERNET not in specification.capabilities:
        message = "Internet access is not enabled. Skipping probe."
        return ProbeResult.success(probe_name, message)

    target_url = "https://example.invalid"
    timeout_seconds = 15

    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.check_hostname = False
    tls_context.verify_mode = ssl.CERT_NONE

    request = urllib.request.Request(target_url, method="GET")

    try:
        with urllib.request.urlopen(
            request, timeout=timeout_seconds, context=tls_context
        ) as response:
            status_code = response.status
    except urllib.error.HTTPError as error:
        if error.code == 403:
            message = f"External HTTPS request to {target_url} was denied by the proxy."
            return ProbeResult.success(probe_name, message)

        message = (
            f"External HTTPS request to {target_url} returned unexpected "
            f"HTTP {error.code}."
        )
        return ProbeResult.failure(probe_name, message)
    except urllib.error.URLError as error:
        reason = str(error.reason)
        if "403" in reason and "Forbidden" in reason:
            message = f"External HTTPS request to {target_url} was denied by the proxy."
            return ProbeResult.success(probe_name, message)

        message = (
            f"Could not confirm proxy denial for {target_url}: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)
    except (TimeoutError, OSError) as error:
        message = (
            f"Could not confirm proxy denial for {target_url}: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    message = (
        f"External HTTPS request reached {target_url} and returned HTTP {status_code}."
    )
    return ProbeResult.failure(probe_name, message)


def docker_dns_resolution_works(probe_context: ProbeContext) -> ProbeResult:
    """Ensure Docker DNS is configured, reachable, and resolves the workload alias."""
    probe_name = "container__network__docker_dns_resolution_works"
    if Capability.NETWORK not in probe_context.specification.capabilities:
        return ProbeResult.success(
            probe_name, "Networking is disabled. Skipping probe."
        )

    try:
        resolver_config = Path("/etc/resolv.conf").read_text(encoding="utf-8")
        nameservers = [
            fields[1]
            for line in resolver_config.splitlines()
            if len(fields := line.split()) >= 2 and fields[0] == "nameserver"
        ]
        if nameservers != [_DOCKER_DNS_RESOLVER]:
            return ProbeResult.failure(
                probe_name, "Expected only the Docker DNS resolver."
            )
        errors = _tcp_connection_errors(_DOCKER_DNS_RESOLVER, 53)
        if errors:
            return ProbeResult.failure(
                probe_name, "Docker DNS TCP endpoint is unreachable."
            )
        addresses = _resolve_network_alias(_WORKLOAD_NETWORK_ALIAS)
    except (OSError, ValueError) as error:
        return ProbeResult.failure(
            probe_name, f"Docker DNS verification failed: {error}"
        )

    if not addresses:
        return ProbeResult.failure(
            probe_name, "Docker DNS returned no workload addresses."
        )
    return ProbeResult.success(
        probe_name, "Docker DNS resolves the workload network alias."
    )


def haproxy_alias_resolves(probe_context: ProbeContext) -> ProbeResult:
    """Ensure a localnet-enabled workload can resolve the HAProxy alias."""
    probe_name = "container__network__haproxy_alias_resolves"
    if Capability.LOCALNET not in probe_context.specification.capabilities:
        return ProbeResult.success(probe_name, "Localnet is disabled. Skipping probe.")
    try:
        addresses = _resolve_network_alias(_HAPROXY_NETWORK_ALIAS)
    except (OSError, ValueError) as error:
        return ProbeResult.failure(
            probe_name, f"HAProxy alias resolution failed: {error}"
        )
    if not addresses:
        return ProbeResult.failure(probe_name, "HAProxy alias returned no addresses.")
    return ProbeResult.success(
        probe_name, "HAProxy alias resolves to non-loopback addresses."
    )


def haproxy_alias_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Ensure HAProxy has no DNS record when localnet is disabled."""
    probe_name = "container__network__haproxy_alias_is_absent"
    capabilities = probe_context.specification.capabilities
    if Capability.NETWORK not in capabilities or Capability.LOCALNET in capabilities:
        return ProbeResult.success(
            probe_name, "HAProxy absence check is inapplicable. Skipping probe."
        )
    # Docker DNS availability is checked by the separate DNS probe.
    try:
        socket.getaddrinfo(_HAPROXY_NETWORK_ALIAS, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        absent_codes = {
            socket.EAI_NONAME,
            getattr(socket, "EAI_NODATA", socket.EAI_NONAME),
        }
        if error.errno in absent_codes:
            return ProbeResult.success(probe_name, "HAProxy alias has no DNS record.")
        return ProbeResult.failure(
            probe_name, f"HAProxy DNS lookup failed unexpectedly: {error}"
        )
    except OSError as error:
        return ProbeResult.failure(
            probe_name, f"HAProxy DNS lookup failed unexpectedly: {error}"
        )
    return ProbeResult.failure(
        probe_name, "HAProxy alias resolves although localnet is disabled."
    )


def haproxy_declared_listeners_are_reachable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure every declared HAProxy TCP frontend accepts connections."""
    probe_name = "container__network__haproxy_declared_listeners_are_reachable"
    specification = probe_context.specification
    if Capability.LOCALNET not in specification.capabilities:
        return ProbeResult.success(probe_name, "Localnet is disabled. Skipping probe.")
    if specification.haproxy is None:
        return ProbeResult.failure(probe_name, "HAProxy configuration is missing.")
    for backend in specification.haproxy.backends:
        try:
            errors = _tcp_connection_errors(_HAPROXY_NETWORK_ALIAS, backend.listen_port)
        except OSError as error:
            return ProbeResult.failure(
                probe_name, f"HAProxy listener lookup failed: {error}"
            )
        if errors:
            return ProbeResult.failure(
                probe_name,
                f"HAProxy listener {backend.listen_port} is unreachable: {errors}",
            )
    # A TCP handshake proves frontend availability, not database availability.
    return ProbeResult.success(
        probe_name, "All declared HAProxy TCP listeners accept connections."
    )


def haproxy_undeclared_listener_is_unavailable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure one undeclared HAProxy port refuses connections without scanning."""
    probe_name = "container__network__haproxy_undeclared_listener_is_unavailable"
    specification = probe_context.specification
    if Capability.LOCALNET not in specification.capabilities:
        return ProbeResult.success(probe_name, "Localnet is disabled. Skipping probe.")
    if specification.haproxy is None:
        return ProbeResult.failure(probe_name, "HAProxy configuration is missing.")
    declared_ports = {backend.listen_port for backend in specification.haproxy.backends}
    excluded_ports = declared_ports | {_HAPROXY_HEALTH_PORT}
    port = next(
        (port for port in range(65535, 0, -1) if port not in excluded_ports), None
    )
    if port is None:
        return ProbeResult.success(
            probe_name, "No undeclared TCP ports exist. Skipping probe."
        )
    return _assert_haproxy_port_refused(probe_name, port)


def haproxy_health_endpoint_is_private(probe_context: ProbeContext) -> ProbeResult:
    """Ensure the loopback-only HAProxy health listener is not workload-accessible."""
    probe_name = "container__network__haproxy_health_endpoint_is_private"
    specification = probe_context.specification
    if Capability.LOCALNET not in specification.capabilities:
        return ProbeResult.success(probe_name, "Localnet is disabled. Skipping probe.")
    if specification.haproxy is None:
        return ProbeResult.failure(probe_name, "HAProxy configuration is missing.")
    if any(
        backend.listen_port == _HAPROXY_HEALTH_PORT
        for backend in specification.haproxy.backends
    ):
        return ProbeResult.failure(
            probe_name, "A backend conflicts with the reserved health port."
        )
    return _assert_haproxy_port_refused(probe_name, _HAPROXY_HEALTH_PORT)


def workload_has_no_default_route(probe_context: ProbeContext) -> ProbeResult:
    """Ensure neither IPv4 nor IPv6 provides a usable workload default route."""
    probe_name = "container__network__workload_has_no_default_route"
    try:
        ipv4_routes = Path("/proc/net/route").read_text(encoding="utf-8")
        ipv6_routes = Path("/proc/net/ipv6_route").read_text(encoding="utf-8")
        ipv4_lines = ipv4_routes.splitlines()
        if not ipv4_lines or ipv4_lines[0].split() != [
            "Iface",
            "Destination",
            "Gateway",
            "Flags",
            "RefCnt",
            "Use",
            "Metric",
            "Mask",
            "MTU",
            "Window",
            "IRTT",
        ]:
            raise ValueError("Missing or malformed IPv4 route table header.")
        for entry in ipv4_lines[1:]:
            fields = entry.split()
            if len(fields) != 11:
                raise ValueError("Malformed IPv4 route entry.")
            destination = int(fields[1], 16)
            mask = int(fields[7], 16)
            flags = int(fields[3], 16)
            if destination == 0 and mask == 0 and flags & 1 and not flags & 0x200:
                return ProbeResult.failure(
                    probe_name, "A usable IPv4 default route exists."
                )
        for entry in ipv6_routes.splitlines():
            fields = entry.split()
            if len(fields) != 10:
                raise ValueError("Malformed IPv6 route entry.")
            destination = int(fields[0], 16)
            prefix = int(fields[1], 16)
            flags = int(fields[8], 16)
            # Linux lists unreachable default-route sentinels with RTF_REJECT set.
            if destination == 0 and prefix == 0 and flags & 1 and not flags & 0x200:
                return ProbeResult.failure(
                    probe_name, "A usable IPv6 default route exists."
                )
    except (OSError, ValueError) as error:
        return ProbeResult.failure(
            probe_name, f"Could not inspect workload routes: {error}"
        )
    return ProbeResult.success(
        probe_name, "No usable IPv4 or IPv6 default route exists."
    )


def _resolve_network_alias(alias: str) -> set[str]:
    address_info = socket.getaddrinfo(alias, None, type=socket.SOCK_STREAM)
    addresses = {str(address[4][0]) for address in address_info}
    for address in addresses:
        parsed_address = ipaddress.ip_address(address)
        if parsed_address.is_loopback or parsed_address.is_unspecified:
            raise ValueError(
                f"Network alias {alias} resolved to a loopback or unspecified address."
            )
    return addresses


def _tcp_connection_errors(host: str, port: int) -> list[OSError]:
    address_info = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not address_info:
        raise OSError("No TCP destination addresses were returned.")
    errors: list[OSError] = []
    for family, socket_type, protocol, _, address in address_info:
        try:
            with socket.socket(family, socket_type, protocol) as connection:
                connection.settimeout(_TCP_TIMEOUT_SECONDS)
                connection.connect(address)
            return []
        except OSError as error:
            errors.append(error)
    return errors


def _assert_haproxy_port_refused(probe_name: str, port: int) -> ProbeResult:
    try:
        errors = _tcp_connection_errors(_HAPROXY_NETWORK_ALIAS, port)
    except OSError as error:
        return ProbeResult.failure(probe_name, f"HAProxy port lookup failed: {error}")
    if errors and all(error.errno == errno.ECONNREFUSED for error in errors):
        return ProbeResult.success(
            probe_name, f"HAProxy port {port} refuses connections."
        )
    return ProbeResult.failure(
        probe_name, f"HAProxy port {port} did not refuse connections: {errors}"
    )


def _decode_ipv4_proc_endpoint(encoded_endpoint: str) -> tuple[str, int]:
    encoded_host, encoded_port = encoded_endpoint.split(":", maxsplit=1)
    host_bytes = bytes.fromhex(encoded_host)

    if len(host_bytes) != 4:
        raise ValueError(f"expected four address bytes, found {len(host_bytes)}")

    host = socket.inet_ntoa(host_bytes[::-1])
    port = int(encoded_port, 16)
    return host, port


def _format_listening_endpoints(endpoints: list[tuple[str, str]]) -> str:
    if not endpoints:
        return "none"

    return ", ".join(
        f"{socket_table_name}:{encoded_endpoint}"
        for socket_table_name, encoded_endpoint in sorted(endpoints)
    )


NETWORK_PROBES = ProbeGroup(
    name="network",
    probes=(
        docker_network_alias_resolved,
        only_loopback_network_interface_exists,
        docker_dns_resolver_is_only_listening_tcp_endpoint,
        proxy_configuration_is_absent,
        proxy_configuration_exists,
        external_http_is_blocked,
        external_http_is_allowed,
        disallowed_external_http_is_blocked,
        external_https_is_blocked,
        external_https_is_allowed,
        disallowed_external_https_is_blocked,
        docker_dns_resolution_works,
        haproxy_alias_resolves,
        haproxy_alias_is_absent,
        haproxy_declared_listeners_are_reachable,
        haproxy_undeclared_listener_is_unavailable,
        haproxy_health_endpoint_is_private,
        workload_has_no_default_route,
    ),
)
