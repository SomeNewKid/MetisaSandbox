"""Probes related to the Docker network."""

from __future__ import annotations

import os
import socket
import ssl
import urllib.error
import urllib.request
from pathlib import Path

from metisa_common.models import Capability

from .models import ProbeContext, ProbeGroup, ProbeResult

_WORKLOAD_NETWORK_ALIAS = "metisa-workload"
_DOCKER_DNS_RESOLVER = "127.0.0.11"
_PROXY_ENVIRONMENT_VARIABLES = frozenset(
    {
        "all_proxy",
        "ftp_proxy",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    }
)
_IPV4_LINK_LOCAL_TEST_ADDRESSES = (
    "169.254.0.0",
    "169.254.1.1",
    "169.254.169.254",
    "169.254.255.255",
)
_IPV6_LINK_LOCAL_TEST_ADDRESSES = (
    "fe80::",
    "fe90::1",
    "fea0::1",
    "febf:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
)


def docker_network_alias_resolved(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure the workload's Docker network alias resolves."""
    probe_name = "network__docker_network_alias_resolved"
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
    probe_name = "network__only_loopback_network_interface_exists"
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
    probe_name = "network__docker_dns_resolver_is_only_listening_tcp_endpoint"
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
    probe_name = "network__proxy_configuration_is_absent"
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


def ipv4_udp_socket_creation_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects creation of IPv4 UDP sockets."""
    probe_name = "network__ipv4_udp_socket_creation_is_blocked"

    try:
        udp_socket = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_DGRAM,
        )
    except OSError as error:
        message = (
            f"IPv4 UDP socket creation was blocked: {type(error).__name__}: {error}"
        )
        return ProbeResult.success(probe_name, message)

    try:
        message = "Python permitted creation of an IPv4 UDP socket."
        return ProbeResult.failure(probe_name, message)
    finally:
        udp_socket.close()


def ipv6_udp_socket_creation_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects creation of IPv6 UDP sockets."""
    probe_name = "network__ipv6_udp_socket_creation_is_blocked"

    try:
        udp_socket = socket.socket(
            family=socket.AF_INET6,
            type=socket.SOCK_DGRAM,
        )
    except OSError as error:
        message = (
            f"IPv6 UDP socket creation was blocked: {type(error).__name__}: {error}"
        )
        return ProbeResult.success(probe_name, message)

    try:
        message = "Python permitted creation of an IPv6 UDP socket."
        return ProbeResult.failure(probe_name, message)
    finally:
        udp_socket.close()


def ipv4_all_interfaces_bind_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects IPv4 binds to all interfaces."""
    return _all_interfaces_bind_is_blocked(
        probe_name="network__ipv4_all_interfaces_bind_is_blocked",
        address_family=socket.AF_INET,
        host="0.0.0.0",
    )


def ipv6_all_interfaces_bind_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects IPv6 binds to all interfaces."""
    return _all_interfaces_bind_is_blocked(
        probe_name="network__ipv6_all_interfaces_bind_is_blocked",
        address_family=socket.AF_INET6,
        host="::",
    )


def empty_host_bind_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects binds using an empty host string."""
    return _all_interfaces_bind_is_blocked(
        probe_name="network__empty_host_bind_is_blocked",
        address_family=socket.AF_INET,
        host="",
    )


def unprivileged_port_start_is_1024(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify ports below 1024 require a privileged process."""
    probe_name = "network__unprivileged_port_start_is_1024"
    expected_port = 1024
    sysctl_path = Path("/proc/sys/net/ipv4/ip_unprivileged_port_start")

    try:
        raw_port = sysctl_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        message = f"Could not read {sysctl_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    try:
        actual_port = int(raw_port)
    except ValueError:
        message = f"Invalid unprivileged port start {raw_port!r} at {sysctl_path}."
        return ProbeResult.failure(probe_name, message)

    if actual_port != expected_port:
        message = (
            f"Expected unprivileged ports to start at {expected_port}, "
            f"got {actual_port}."
        )
        return ProbeResult.failure(probe_name, message)

    message = f"Unprivileged ports start at {actual_port}."
    return ProbeResult.success(probe_name, message)


def ipv4_link_local_connections_are_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects connections throughout the IPv4 link-local range."""
    return _connections_are_blocked(
        probe_name="network__ipv4_link_local_connections_are_blocked",
        address_family=socket.AF_INET,
        hosts=_IPV4_LINK_LOCAL_TEST_ADDRESSES,
    )


def ipv6_link_local_connections_are_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects connections throughout the IPv6 link-local range."""
    return _connections_are_blocked(
        probe_name="network__ipv6_link_local_connections_are_blocked",
        address_family=socket.AF_INET6,
        hosts=_IPV6_LINK_LOCAL_TEST_ADDRESSES,
    )


def aws_ipv6_metadata_connection_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects connections to the AWS IPv6 metadata endpoint."""
    return _connections_are_blocked(
        probe_name="network__aws_ipv6_metadata_connection_is_blocked",
        address_family=socket.AF_INET6,
        hosts=("fd00:ec2::254",),
    )


def google_ipv6_metadata_connection_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects connections to the Google IPv6 metadata endpoint."""
    return _connections_are_blocked(
        probe_name="network__google_ipv6_metadata_connection_is_blocked",
        address_family=socket.AF_INET6,
        hosts=("fd20:ce::254",),
    )


def google_metadata_hostname_connection_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects the Google metadata hostname before resolution."""
    return _connections_are_blocked(
        probe_name="network__google_metadata_hostname_connection_is_blocked",
        address_family=socket.AF_INET,
        hosts=("metadata.google.internal",),
    )


def external_http_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure outbound unsecured HTTP access is unavailable."""
    probe_name = "docker__external_http_is_blocked"
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


def external_https_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure outbound HTTPS access is unavailable."""
    probe_name = "network__external_https_is_blocked"
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


def _all_interfaces_bind_is_blocked(
    probe_name: str,
    address_family: socket.AddressFamily,
    host: str,
) -> ProbeResult:
    try:
        test_socket = socket.socket(
            family=address_family,
            type=socket.SOCK_STREAM,
        )
    except OSError as error:
        message = (
            f"Could not create the test socket for host {host!r}: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    with test_socket:
        try:
            test_socket.bind((host, 0))
        except OSError as error:
            message = (
                f"Bind to all interfaces using host {host!r} was blocked: "
                f"{type(error).__name__}: {error}"
            )
            return ProbeResult.success(probe_name, message)

    message = f"Python permitted a bind to all interfaces using host {host!r}."
    return ProbeResult.failure(probe_name, message)


def _connections_are_blocked(
    probe_name: str,
    address_family: socket.AddressFamily,
    hosts: tuple[str, ...],
) -> ProbeResult:
    port = 80
    timeout_seconds = 1.0

    for host in hosts:
        try:
            test_socket = socket.socket(
                family=address_family,
                type=socket.SOCK_STREAM,
            )
        except OSError as error:
            message = (
                f"Could not create the test socket for host {host!r}: "
                f"{type(error).__name__}: {error}"
            )
            return ProbeResult.failure(probe_name, message)

        with test_socket:
            test_socket.settimeout(timeout_seconds)

            try:
                test_socket.connect((host, port))
            except PermissionError:
                continue
            except OSError as error:
                message = (
                    f"Connection to {host!r} failed without a policy rejection: "
                    f"{type(error).__name__}: {error}"
                )
                return ProbeResult.failure(probe_name, message)

        message = f"Python permitted a connection to {host!r}."
        return ProbeResult.failure(probe_name, message)

    tested_hosts = ", ".join(hosts)
    message = f"Python rejected connections to: {tested_hosts}."
    return ProbeResult.success(probe_name, message)


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
        ipv4_udp_socket_creation_is_blocked,
        ipv6_udp_socket_creation_is_blocked,
        ipv4_all_interfaces_bind_is_blocked,
        ipv6_all_interfaces_bind_is_blocked,
        empty_host_bind_is_blocked,
        unprivileged_port_start_is_1024,
        ipv4_link_local_connections_are_blocked,
        ipv6_link_local_connections_are_blocked,
        aws_ipv6_metadata_connection_is_blocked,
        google_ipv6_metadata_connection_is_blocked,
        google_metadata_hostname_connection_is_blocked,
        external_http_is_blocked,
        external_https_is_blocked,
    ),
)
