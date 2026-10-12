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
#  private workload network          egress network
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
#  private workload network          egress network
#  ┌────────────────────────┐        ┌─────────────────────────┐
#  │ Workload ──> HAProxy   │        │ HAProxy   ──> Localnet  │
#  │              interface ├───┬────┤ interface     (MariaDB) │
#  └────────────────────────┘   │    └─────────────────────────┘
#                               │
#                               │    ┌─────────────────────────┐
#                               │    │ Squid     ──> Internet  │
#                               └────┤ interface               │
#                                    └─────────────────────────┘
#
# 1. The workload resolves `metisa-haproxy` on its private network.
# 2. The workload opens a TCP connection to HAProxy on a configured listener port.
# 3. HAProxy opens a separate outbound connection through its egress-network interface.
# 4. HAProxy relays application data between those two connections.
#
# -----------------------------------------------------------------------------------
#
# When the "MCP_SERVER" capability is decalred, a backend network is created.
# The MCP Server is the connection between the workload and backend networks.
# The HAProxy is the connection between the backend and egress networks.
# Both the MCP Server and the HAProxy are "dual homed".
#
#  private workload network          private backend network            egress network
#  ┌────────────────────────┐        ┌─────────────────────────┐        ┌─────────────────────────┐  # noqa: E501
#  │ Workload ──> MCP       │        │ MCP     ──>   HAProxy   │        │ HAProxy   ──> Localnet  │  # noqa: E501
#  │              Server    ├───┬────┤ server        interface ├────────┤ interface     (MariaDB) │  # noqa: E501
#  └────────────────────────┘   │    └─────────────────────────┘        └─────────────────────────┘  # noqa: E501
#                               │                                                                    # noqa: E501
#                               │                                       ┌─────────────────────────┐  # noqa: E501
#                               │                                       │ Squid     ──> Internet  │  # noqa: E501
#                               └───────────────────────────────────────┤ interface               │  # noqa: E501
#                                                                       └─────────────────────────┘  # noqa: E501
#
# -----------------------------------------------------------------------------------


def create_docker_workload_network(
    sandbox_context: SandboxContext,
) -> None:
    """Create a private Docker network for the workload."""
    create_docker_network(
        network_name=sandbox_context.workload_network_name,
        internal=True,
    )


def create_docker_backend_network(
    sandbox_context: SandboxContext,
) -> None:
    """Create a private Docker network for the backend."""
    create_docker_network(
        network_name=sandbox_context.backend_network_name,
        internal=True,
    )


def create_docker_egress_network(
    sandbox_context: SandboxContext,
) -> None:
    """Create an egress Docker network."""
    create_docker_network(
        network_name=sandbox_context.egress_network_name,
        internal=False,
    )


def remove_docker_workload_network(
    sandbox_context: SandboxContext,
) -> None:
    """Remove the Docker internal network for the workload."""
    remove_docker_network(sandbox_context.workload_network_name)


def remove_docker_backend_network(
    sandbox_context: SandboxContext,
) -> None:
    """Remove the Docker internal network for the backend."""
    remove_docker_network(sandbox_context.backend_network_name)


def remove_docker_egress_network(
    sandbox_context: SandboxContext,
) -> None:
    """Remove the Docker egress network."""
    remove_docker_network(sandbox_context.egress_network_name)
