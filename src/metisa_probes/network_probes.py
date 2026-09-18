"""Probes related to the Docker network."""

from __future__ import annotations

import socket
import ssl
import urllib.error
import urllib.request

from metisa_common.models import Capability

from .models import ProbeContext, ProbeGroup, ProbeResult

_WORKLOAD_NETWORK_ALIAS = "metisa-workload"


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


NETWORK_PROBES = ProbeGroup(
    name="network",
    probes=(
        docker_network_alias_resolved,
        only_loopback_network_interface_exists,
        external_http_is_blocked,
        external_https_is_blocked,
    ),
)
