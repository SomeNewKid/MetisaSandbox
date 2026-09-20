"""Probes related to the workload environment."""

from __future__ import annotations

import os

from .models import ProbeContext, ProbeGroup, ProbeResult

_HOST_CHANNEL_ENVIRONMENT_VARIABLES = (
    "SSH_AUTH_SOCK",
    "GPG_AGENT_INFO",
    "DBUS_SESSION_BUS_ADDRESS",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XAUTHORITY",
)


def host_channel_environment_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify host-channel environment variables are absent."""
    probe_name = "environment__host_channel_environment_is_absent"
    configured_variables = sorted(
        variable_name
        for variable_name in _HOST_CHANNEL_ENVIRONMENT_VARIABLES
        if variable_name in os.environ
    )

    if configured_variables:
        variables = ", ".join(configured_variables)
        message = f"Host-channel environment variables are configured: {variables}."
        return ProbeResult.failure(probe_name, message)

    message = "No host-channel environment variables are configured."
    return ProbeResult.success(probe_name, message)


ENVIRONMENT_PROBES = ProbeGroup(
    name="environment",
    probes=(host_channel_environment_is_absent,),
)
