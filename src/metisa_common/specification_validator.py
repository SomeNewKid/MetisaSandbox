"""Validate a Metisa TOML specification."""

from __future__ import annotations

import re

from .specification_models import (
    Capability,
    HaproxySpecification,
    McpServerSpecification,
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

    _validate_haproxy_specification(
        specification.capabilities,
        specification.haproxy,
    )

    _validate_mcp_server_specification(
        specification.capabilities,
        specification.mcp_server,
    )

    _validate_ollama_sidecar_specification(
        specification.capabilities,
        specification.ollama_sidecar,
    )


def is_valid_domain_name(
    value: str,
    suffix_domain_ok: bool = False,
) -> bool:
    """Determine whether value is a valid domain name."""
    if not value:
        return False
    stripped_value = value.strip()
    if len(stripped_value) != len(value):
        return False
    if value.startswith("."):
        if not suffix_domain_ok:
            return False
        value = value[1:]
    parts = value.split(".")
    for part in parts:
        if not _is_valid_domain_name_part(part):
            return False
    return True


def is_valid_ip_address(
    value: str,
) -> bool:
    """Determine whether value is a valid IPv4 or IPv6 address."""
    return is_valid_ipv4_address(value) or is_valid_ipv6_address(value)


def is_valid_ipv4_address(
    value: str,
) -> bool:
    """Determine whether value is a valid IPv4 address."""
    if not value:
        return False
    stripped_value = value.strip()
    if len(stripped_value) != len(value):
        return False
    parts = value.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not _is_valid_ipv4_part(part):
            return False
    return True


def is_valid_ipv6_address(
    value: str,
) -> bool:
    """Determine whether value is a valid IPv6 address."""
    if not value:
        return False
    stripped_value = value.strip()
    if len(stripped_value) != len(value):
        return False
    parts = value.split(":")
    last_part = parts[-1]
    last_part_is_ipv4_address = is_valid_ipv4_address(last_part)
    if last_part_is_ipv4_address:
        parts = parts[0:-1]
    number_of_parts = len(parts)
    if last_part_is_ipv4_address:
        if number_of_parts > 7:
            return False
    else:
        if number_of_parts > 8:
            return False
    number_compression_markers = value.count("::")
    if number_compression_markers > 1:  # compression markers
        return False
    if (number_compression_markers == 0) and (number_of_parts != 8):
        return False

    for part in parts:
        if not _is_valid_ipv6_part(part):
            return False
    return True


def _validate_capabilities(
    capabilities: frozenset[Capability],
):
    if Capability.INTERNET in capabilities:
        if Capability.NETWORK not in capabilities:
            raise SpecificationValidationError(
                '"internet" capability requires "network" capability.'
            )

    if Capability.LOCALNET in capabilities:
        if Capability.NETWORK not in capabilities:
            raise SpecificationValidationError(
                '"localnet" capability requires "network" capability.'
            )

    if Capability.MCP_CLIENT in capabilities:
        if Capability.NETWORK not in capabilities:
            raise SpecificationValidationError(
                '"mcp_client" capability requires "network" capability.'
            )


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

    for value in squid_proxy_specification.allowed_domains:
        if not is_valid_domain_name(value, suffix_domain_ok=True):
            raise SpecificationValidationError(
                f"[squid_proxy] table had invalid allowed domain: {value}"
            )

    for value in squid_proxy_specification.allowed_ip_addresses:
        if not is_valid_ip_address(value):
            raise SpecificationValidationError(
                f"[squid_proxy] table had invalid allowed IP address: {value}"
            )


def _validate_haproxy_specification(
    capabilities: frozenset[Capability],
    haproxy_specification: HaproxySpecification | None,
):
    if haproxy_specification is None:
        return

    if Capability.LOCALNET not in capabilities:
        raise SpecificationValidationError(
            '"[haproxy]" table requires "localnet" capability.'
        )

    listen_ports: list[int] = []
    conflicted_ports: list[int] = []
    for backend in haproxy_specification.backends:
        listen_port = backend.listen_port
        if listen_port in listen_ports:
            if listen_port not in conflicted_ports:
                conflicted_ports.append(listen_port)
        else:
            listen_ports.append(listen_port)

    if conflicted_ports:
        plural = "s" if len(conflicted_ports) > 1 else ""
        csv = ", ".join(str(port) for port in conflicted_ports)
        error = f"HAProxy backend conflict on port{plural}: {csv}"
        raise SpecificationValidationError(error)


def _validate_mcp_server_specification(
    capabilities: frozenset[Capability],
    mcp_server_specification: McpServerSpecification | None,
):
    if mcp_server_specification is None:
        return

    if Capability.MCP_CLIENT not in capabilities:
        raise SpecificationValidationError(
            '"[mcp_server]" table requires "mcp_client" capability.'
        )


def _validate_ollama_sidecar_specification(
    capabilities: frozenset[Capability],
    ollama_sidecar_specification: OllamaSidecarSpecification | None,
):
    if ollama_sidecar_specification is None:
        return


def _is_valid_domain_name_part(
    part: str,
) -> bool:
    stripped_part = part.strip()
    if len(stripped_part) != len(part):
        return False
    length_of_part = len(part)
    if (length_of_part < 1) or (length_of_part > 63):
        return False
    if length_of_part == 1:
        pattern = "^[a-zA-Z]$"  # must be a letter
    elif length_of_part == 2:
        pattern = (
            "^[a-zA-Z]"  # start with a letter
            "[a-zA-Z0-9]$"  # end with a letter or digit
        )
    else:
        pattern = (
            "^[a-zA-Z]"  # start with a letter
            "[a-zA-Z0-9-]+"  # letters, digits, hypens
            "[a-zA-Z0-9]$"  # end with a letter or digit
        )
    return bool(re.match(pattern, part))


def _is_valid_ipv4_part(
    part: str,
) -> bool:
    stripped_part = part.strip()
    if len(stripped_part) != len(part):
        return False
    length_of_part = len(part)
    if (length_of_part < 1) or (length_of_part > 3):
        return False
    if part.startswith("0") and (length_of_part > 1):
        return False
    pattern = "^[0-9]+$"
    if not bool(re.match(pattern, part)):
        return False
    value: int | None = None
    try:
        value = int(part)
    except ValueError:
        return False
    return (value >= 0) and (value <= 255)


def _is_valid_ipv6_part(
    part: str,
) -> bool:
    stripped_part = part.strip()
    if len(stripped_part) != len(part):
        return False
    if len(part) == 0:
        return True
    length_of_part = len(part)
    if length_of_part > 4:
        return False
    pattern = "^[0-9a-fA-F]+$"
    if not bool(re.match(pattern, part)):
        return False
    return True
