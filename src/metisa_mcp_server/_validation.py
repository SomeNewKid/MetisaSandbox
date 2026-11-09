"""Provide validation utilities for the Metisa MCP Server."""

from __future__ import annotations

import re
from ipaddress import IPv4Address, IPv6Address, ip_address
from urllib.parse import urlsplit

from metisa_common.clients.prompt_guard_client import (
    classify_text,
)


# This is a pre-emptive guard to ensure that filename arguments are valid and safe.
# The real guard will be implemented by the downstream service.
def validate_filename_argument(
    filename: str,
) -> None:
    """Validate the given filename argument."""
    if not filename:
        raise ValueError("Filename must be provided.")

    if "\x00" in filename:
        raise ValueError("Filename must not contain null characters.")

    if filename.startswith("/"):
        raise ValueError("Filename must be a relative path.")

    if "\\" in filename:
        raise ValueError("Filename must use forward slashes.")

    if ":" in filename:
        raise ValueError("Filename must not contain a colon.")

    components = filename.split("/")

    if any(component in ("", ".", "..") for component in components):
        raise ValueError(
            "Filename must not contain empty, '.' or '..' path components."
        )


def validate_url_argument(
    url: str,
) -> None:
    """Validate the given URL argument."""
    if not url:
        raise ValueError("URL must be provided.")

    # Reject characters that URL parsers or clients may interpret differently
    if "\\" in url:
        raise ValueError("URL must not contain backslashes.")

    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in url
    ):
        raise ValueError("URL must not contain whitespace or control characters.")

    try:
        parsed = urlsplit(url)
        scheme = parsed.scheme
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError("URL has an invalid hostname or port.") from error

    if scheme not in ("http", "https"):
        raise ValueError("URL must use HTTP or HTTPS.")

    if not hostname:
        raise ValueError("URL must include a hostname.")

    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL must not include credentials.")

    if port is not None and not 1 <= port <= 65535:
        raise ValueError("URL port must be between 1 and 65535.")

    if "%" in hostname:
        raise ValueError("URL hostname must not contain percent signs.")

    hostname = hostname.rstrip(".").lower()

    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("URL must not refer to localhost.")

    try:
        address = ip_address(hostname)
    except ValueError:
        _validate_hostname_syntax(hostname)
    else:
        _validate_public_address(address)


def validate_text_result(
    text: str,
) -> None:
    if not text or not text.strip():
        return

    classification = classify_text(text)
    if classification["indicators"]:
        error = "Tool result was blocked because Prompt Guard reported indicators."
        raise RuntimeError(error)


def _validate_hostname_syntax(
    hostname: str,
) -> None:
    if not hostname or len(hostname) > 253:
        raise ValueError("URL hostname has an invalid length.")

    labels = hostname.split(".")

    for label in labels:
        if (
            re.fullmatch(
                r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
                label,
            )
            is None
        ):
            raise ValueError("URL hostname contains an invalid label.")

    final_label = labels[-1]

    if final_label.isdecimal() or re.fullmatch(r"0x[0-9a-f]+", final_label) is not None:
        raise ValueError("URL must not use a nonstandard numeric address.")


def _validate_public_address(
    address: IPv4Address | IPv6Address,
) -> None:
    if isinstance(address, IPv6Address):
        if address.is_site_local:
            raise ValueError("URL must not refer to a site-local address.")

        mapped_address = address.ipv4_mapped
        if mapped_address is not None:
            address = mapped_address

    # Using is_global implements a stricter policy than merely rejecting is_private:
    # it also excludes addresses such as unspecified and shared-address space.
    if not address.is_global or address.is_multicast:
        raise ValueError("URL must refer to a public, non-multicast address.")
