"""Probes related to the workload environment."""

from __future__ import annotations

import os

from ..probe_models import ProbeContext, ProbeGroup, ProbeResult

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
    probe_name = "container__environment__host_channel_environment_is_absent"
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


def declared_literal_environment_is_available(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the declared literal probe variable has the expected diagnostic value."""
    probe_name = "container__environment__declared_literal_environment_is_available"
    variable_name = "METISA_PROBE_1"

    if not _environ_is_declared(probe_context, variable_name):
        message = f"{variable_name} is not declared. Skipping probe."
        return ProbeResult.success(probe_name, message)

    value = os.environ.get(variable_name)
    if not value:
        message = f"{variable_name} is missing or empty."
        return ProbeResult.failure(probe_name, message)

    expected_value = "hard-coded value"
    if value != expected_value:
        message = f"{variable_name} does not match the expected diagnostic value."
        return ProbeResult.failure(probe_name, message)

    message = f"{variable_name} matches the expected diagnostic value."
    return ProbeResult.success(probe_name, message)


def declared_host_environment_is_resolved(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the declared host probe variable has the expected diagnostic value."""
    probe_name = "container__environment__declared_host_environment_is_resolved"
    variable_name = "METISA_PROBE_2"

    if not _environ_is_declared(probe_context, variable_name):
        message = f"{variable_name} is not declared. Skipping probe."
        return ProbeResult.success(probe_name, message)

    value = os.environ.get(variable_name)
    if not value:
        message = f"{variable_name} is missing or empty."
        return ProbeResult.failure(probe_name, message)

    expected_value = "Retrieved from host's environment variables"
    if value != expected_value:
        message = f"{variable_name} does not match the expected diagnostic value."
        return ProbeResult.failure(probe_name, message)

    message = f"{variable_name} matches the expected diagnostic value."
    return ProbeResult.success(probe_name, message)


ENVIRONMENT_PROBES = ProbeGroup(
    name="environment",
    probes=(
        host_channel_environment_is_absent,
        declared_literal_environment_is_available,
        declared_host_environment_is_resolved,
    ),
)


def _environ_is_declared(
    probe_context: ProbeContext,
    variable_name: str,
) -> bool:
    for environ in probe_context.specification.environs:
        declared_name, _, _ = environ.partition("=")
        if declared_name == variable_name:
            return True

    return False
