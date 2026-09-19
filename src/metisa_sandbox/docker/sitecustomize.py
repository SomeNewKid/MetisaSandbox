"""Customize Python in the hardened Docker container.

A sitecustomize.py file is a special script that automatically executes
every time the Python interpreter starts up.
It is a built-in configuration hook provided by Python's core site module
to allow system administrators or tools to perform global,
environment-wide customizations before any other user script runs.
"""

import ipaddress
import socket
from typing import Any

_original_socket = socket.socket
_BLOCKED_HOSTNAMES = frozenset({"metadata.google.internal"})
_BLOCKED_IP_ADDRESSES = frozenset(
    {
        ipaddress.ip_address("fd00:ec2::254"),
        ipaddress.ip_address("fd20:ce::254"),
    }
)
_IPV4_LINK_LOCAL_NETWORK = ipaddress.ip_network("169.254.0.0/16")
_IPV6_LINK_LOCAL_NETWORK = ipaddress.ip_network("fe80::/10")


class GuardedSocket(_original_socket):
    """Apply the Metisa Python socket restrictions."""

    def __init__(
        self,
        family: int = socket.AF_INET,
        type: int = socket.SOCK_STREAM,
        proto: int = 0,
        fileno: int | None = None,
    ) -> None:
        """Create a socket unless its family and type are prohibited."""
        socket_type = type & 0x0F

        if (
            family in (socket.AF_INET, socket.AF_INET6)
            and socket_type == socket.SOCK_DGRAM
        ):
            raise PermissionError("IPv4 and IPv6 UDP sockets are disabled.")

        super().__init__(family, type, proto, fileno)

    def bind(self, address: Any) -> None:
        """Reject IPv4 and IPv6 binds to all interfaces."""
        if self.family in (socket.AF_INET, socket.AF_INET6):
            host = address[0]

            if host == "" or host == b"":
                raise PermissionError("Binding to all network interfaces is disabled.")

            normalized_host = host

            if isinstance(host, bytes):
                try:
                    normalized_host = host.decode("ascii")
                except UnicodeDecodeError:
                    normalized_host = host

            try:
                ip_address = ipaddress.ip_address(normalized_host)
            except (TypeError, ValueError):
                ip_address = None

            if ip_address is not None and ip_address.is_unspecified:
                raise PermissionError("Binding to all network interfaces is disabled.")

        super().bind(address)

    def connect(self, address: Any) -> None:
        """Reject connections to prohibited IPv4, IPv6, and named hosts."""
        self._reject_blocked_destination(address)
        super().connect(address)

    def connect_ex(self, address: Any) -> int:
        """Reject prohibited destinations before returning a connection status."""
        self._reject_blocked_destination(address)
        return super().connect_ex(address)

    def _reject_blocked_destination(self, address: Any) -> None:
        if self.family not in (socket.AF_INET, socket.AF_INET6):
            return

        host = _normalize_host(address[0])

        if host is None:
            return

        hostname = host.rstrip(".").lower()

        if hostname in _BLOCKED_HOSTNAMES:
            raise PermissionError(f"Connections to {host!r} are disabled.")

        address_text = host.split("%", maxsplit=1)[0]

        try:
            ip_address = ipaddress.ip_address(address_text)
        except ValueError:
            return

        comparable_address = ip_address

        if isinstance(ip_address, ipaddress.IPv6Address):
            ipv4_address = ip_address.ipv4_mapped

            if ipv4_address is not None:
                comparable_address = ipv4_address

        if (
            comparable_address in _IPV4_LINK_LOCAL_NETWORK
            or comparable_address in _IPV6_LINK_LOCAL_NETWORK
            or ip_address in _BLOCKED_IP_ADDRESSES
        ):
            raise PermissionError(f"Connections to {host!r} are disabled.")


def _normalize_host(host: Any) -> str | None:
    if isinstance(host, str):
        return host

    if isinstance(host, bytes):
        try:
            return host.decode("ascii")
        except UnicodeDecodeError:
            return None

    return None


socket.socket = GuardedSocket
