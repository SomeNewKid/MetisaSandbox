"""Utility functions for managing the Docker sandbox network."""

from __future__ import annotations

from .docker.docker_network import create_docker_network, remove_docker_network
from .sandbox_context import SandboxContext

# -----------------------------------------------------------------------------------
#
# When the "NETWORK" capability is decalred, a private network is created.
#
#  private network
#  ┌────────────────────────┐
#  │ Workload               │
#  │                        │
#  └────────────────────────┘
#
# -----------------------------------------------------------------------------------
#
# When the "INTERNET" capability is decalred, an egress network is created.
# The Squid Proxy is the connection between the two networks.
# The Squid Proxy is attached to both, making it "dual homed".
#
#  private network                   egress network
#  ┌────────────────────────┐        ┌─────────────────────────┐
#  │ Workload ──> Squid     │        │ Squid     ──> Internet  │
#  │              interface ├────────┤ interface               │
#  └────────────────────────┘        └─────────────────────────┘
#
# 1. The workload resolves `metisa-squid` on its private network.
# 2. The workload opens a TCP connection to Squid on port `3128`.
# 3. Squid receives the HTTP or HTTPS `CONNECT` request.
# 4. Squid opens a separate outbound connection through its egress-network interface.
# 5. Squid relays application data between those two connections.
#
# -----------------------------------------------------------------------------------
#
# When the "LOCALNET" capability is decalred, an egress network is created.
# The HAProxy is the connection between the two networks.
# The HAProxy is attached to both, making it "dual homed".
#
#  private network                   egress network
#  ┌────────────────────────┐        ┌─────────────────────────┐
#  │ Workload ──> HAProxy   │        │ HAProxy   ──> Localnet  │
#  │              interface ├────────┤ interface     (MariaDB) │
#  └────────────────────────┘        └─────────────────────────┘
#
# 1. The workload resolves `metisa-haproxy` on its private network.
# 2. The workload opens a TCP connection to HAProxy on a configured listener port.
# 3. HAProxy opens a separate outbound connection through its egress-network interface.
# 4. HAProxy relays application data between those two connections.
#
# -----------------------------------------------------------------------------------


def create_docker_private_network(
    sandbox_context: SandboxContext,
) -> None:
    """Create a private Docker network for the sandbox context."""
    create_docker_network(
        network_name=sandbox_context.private_network_name,
        internal=True,
    )


def create_docker_egress_network(
    sandbox_context: SandboxContext,
) -> None:
    """Create an egress Docker network for the sandbox context."""
    create_docker_network(
        network_name=sandbox_context.egress_network_name,
        internal=False,
    )


def remove_docker_private_network(
    sandbox_context: SandboxContext,
) -> None:
    """Remove the Docker internal network for the sandbox context."""
    remove_docker_network(sandbox_context.private_network_name)


def remove_docker_egress_network(
    sandbox_context: SandboxContext,
) -> None:
    """Remove the Docker egress network for the sandbox context."""
    remove_docker_network(sandbox_context.egress_network_name)
