"""Probes related to Python socket defense-in-depth controls."""

from __future__ import annotations

import socket

from ..models import ProbeContext, ProbeGroup, ProbeResult

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


def ipv4_udp_socket_creation_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects creation of IPv4 UDP sockets."""
    probe_name = "python__probes__ipv4_udp_socket_creation_is_blocked"

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
    probe_name = "python__probes__ipv6_udp_socket_creation_is_blocked"

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
        probe_name="python__probes__ipv4_all_interfaces_bind_is_blocked",
        address_family=socket.AF_INET,
        host="0.0.0.0",
    )


def ipv6_all_interfaces_bind_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects IPv6 binds to all interfaces."""
    return _all_interfaces_bind_is_blocked(
        probe_name="python__probes__ipv6_all_interfaces_bind_is_blocked",
        address_family=socket.AF_INET6,
        host="::",
    )


def empty_host_bind_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects binds using an empty host string."""
    return _all_interfaces_bind_is_blocked(
        probe_name="python__probes__empty_host_bind_is_blocked",
        address_family=socket.AF_INET,
        host="",
    )


def ipv4_link_local_connections_are_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects connections throughout the IPv4 link-local range."""
    return _connections_are_blocked(
        probe_name="python__probes__ipv4_link_local_connections_are_blocked",
        address_family=socket.AF_INET,
        hosts=_IPV4_LINK_LOCAL_TEST_ADDRESSES,
    )


def ipv6_link_local_connections_are_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects connections throughout the IPv6 link-local range."""
    return _connections_are_blocked(
        probe_name="python__probes__ipv6_link_local_connections_are_blocked",
        address_family=socket.AF_INET6,
        hosts=_IPV6_LINK_LOCAL_TEST_ADDRESSES,
    )


def aws_ipv6_metadata_connection_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects connections to the AWS IPv6 metadata endpoint."""
    return _connections_are_blocked(
        probe_name="python__probes__aws_ipv6_metadata_connection_is_blocked",
        address_family=socket.AF_INET6,
        hosts=("fd00:ec2::254",),
    )


def google_ipv6_metadata_connection_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects connections to the Google IPv6 metadata endpoint."""
    return _connections_are_blocked(
        probe_name="python__probes__google_ipv6_metadata_connection_is_blocked",
        address_family=socket.AF_INET6,
        hosts=("fd20:ce::254",),
    )


def google_metadata_hostname_connection_is_blocked(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python rejects the Google metadata hostname before resolution."""
    return _connections_are_blocked(
        probe_name="python__probes__google_metadata_hostname_connection_is_blocked",
        address_family=socket.AF_INET,
        hosts=("metadata.google.internal",),
    )


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


SOCKET_PROBES = ProbeGroup(
    name="socket",
    probes=(
        ipv4_udp_socket_creation_is_blocked,
        ipv6_udp_socket_creation_is_blocked,
        ipv4_all_interfaces_bind_is_blocked,
        ipv6_all_interfaces_bind_is_blocked,
        empty_host_bind_is_blocked,
        ipv4_link_local_connections_are_blocked,
        ipv6_link_local_connections_are_blocked,
        aws_ipv6_metadata_connection_is_blocked,
        google_ipv6_metadata_connection_is_blocked,
        google_metadata_hostname_connection_is_blocked,
    ),
)
