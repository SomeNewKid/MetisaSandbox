"""Utility functions for managing the Docker sandbox network."""

from __future__ import annotations

from metisa_common.terminal_helper import (
    terminal_status,
)

from ._docker._docker_network import create_docker_network, remove_docker_network
from ._sandbox_models import SandboxNetwork

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
#  └────────────────────────┘   │    └───┬─────────────────────┘        └─────────────────────────┘  # noqa: E501
#                               │        │                                                           # noqa: E501
#                               │        │                              ┌─────────────────────────┐  # noqa: E501
#                               │        │                              │ Squid     ──> Internet  │  # noqa: E501
#                               └────────┴──────────────────────────────┤ interface               │  # noqa: E501
#                                                                       └─────────────────────────┘  # noqa: E501
#
# -----------------------------------------------------------------------------------


def define_sandbox_network(
    short_name: str,
    instance_name: str,
    is_internal: bool,
) -> SandboxNetwork:
    """Define a new sandbox network."""
    return SandboxNetwork(
        f"{short_name} network", name=instance_name, is_internal=is_internal
    )


def create_sandbox_network(
    network: SandboxNetwork,
) -> None:
    """Create the specified sandbox network if it does not already exist."""
    if network.is_created:
        return

    with terminal_status(
        running=f"Creating {network.title}...",
        success=f"Created {network.title}.",
        failure=f"Could not create {network.title}.",
    ):
        create_docker_network(network.name, internal=network.is_internal)
        network.set_created()


def remove_sandbox_networks(
    sandbox_networks: list[SandboxNetwork],
    cleanup_errors: list[str],
) -> None:
    """Remove all specified sandbox networks."""
    for sandbox_network in sandbox_networks:
        _remove_sandbox_network(sandbox_network, cleanup_errors)


def _remove_sandbox_network(
    sandbox_network: SandboxNetwork,
    cleanup_errors: list[str],
) -> None:
    if not sandbox_network.is_created:
        return

    try:
        with terminal_status(
            running=f"Removing network {sandbox_network.title}...",
            success=f"Removed network {sandbox_network.title}.",
            failure=f"Could not remove {sandbox_network.title}.",
        ):
            remove_docker_network(sandbox_network.name)
            sandbox_network.set_removed()
    except Exception as error:
        cleanup_error = f"Could not remove network '{sandbox_network.title}': {error}"
        cleanup_errors.append(cleanup_error)
