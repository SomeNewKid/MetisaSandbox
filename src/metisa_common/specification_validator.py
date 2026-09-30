"""Validate a Metisa TOML specification."""

from __future__ import annotations

from .models import (
    Capability,
    HaproxySpecification,
    McpSidecarSpecification,
    MetisaSpecification,
    OllamaSidecarSpecification,
    SpecificationValidationError,
    SquidProxySpecification,
)


def validate_specification(
    specification: MetisaSpecification,
) -> None:
    """Validate a Metisa TOML specification."""
    _validate_capabilities(specification.capabilities)

    _validate_squid_proxy_specification(
        specification.capabilities,
        specification.squid_proxy,
    )

    _validate_ha_proxy_specification(
        specification.capabilities,
        specification.haproxy,
    )

    _validate_mcp_sidecar_specification(
        specification.capabilities,
        specification.mcp_sidecar,
    )

    _validate_ollama_sidecar_specification(
        specification.capabilities,
        specification.ollama_sidecar,
    )


def _validate_capabilities(
    capabilities: frozenset[Capability],
):
    if Capability.INTERNET in capabilities:
        if Capability.NETWORK not in capabilities:
            raise SpecificationValidationError(
                '"internet" capability requires "network" capability.'
            )
        pass


def _validate_squid_proxy_specification(
    capabilities: frozenset[Capability],
    squid_proxy_specification: SquidProxySpecification | None,
):
    if squid_proxy_specification is None:
        return

    if Capability.INTERNET not in capabilities:
        raise SpecificationValidationError(
            '"[squid_proxy]" table requires "internet" capability.'
        )
    pass


def _validate_ha_proxy_specification(
    capabilities: frozenset[Capability],
    haproxy_specification: HaproxySpecification | None,
):
    if haproxy_specification is None:
        return
    pass


def _validate_mcp_sidecar_specification(
    capabilities: frozenset[Capability],
    mcp_sidecar_specification: McpSidecarSpecification | None,
):
    if mcp_sidecar_specification is None:
        return
    pass


def _validate_ollama_sidecar_specification(
    capabilities: frozenset[Capability],
    ollama_sidecar_specification: OllamaSidecarSpecification | None,
):
    if ollama_sidecar_specification is None:
        return
    pass
