from __future__ import annotations

import json

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import SpecificationValidationError


def test_squid_proxy_missing_details() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is None


def test_squid_proxy_with_unknown_key() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        unknown = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_squid_proxy_invalid_if_internet_capability_but_no_network_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "internet",
        ]

        [squid_proxy]
        allowed_domains = []
        allowed_ip_addresses = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_squid_proxy_invalid_if_no_internet_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
        ]

        [squid_proxy]
        allowed_domains = []
        allowed_ip_addresses = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_squid_proxy_missing_allowed_domains() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        allowed_ip_addresses = []
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is not None
    assert len(specification.squid_proxy.allowed_domains) == 0
    assert len(specification.squid_proxy.allowed_ip_addresses) == 0


def test_squid_proxy_empty_allowed_domains() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        allowed_domains = []
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is not None
    assert len(specification.squid_proxy.allowed_domains) == 0
    assert len(specification.squid_proxy.allowed_ip_addresses) == 0


def test_squid_proxy_populated_allowed_domains() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        allowed_domains = [
            ".example.com"
        ]
        allowed_ip_addresses = []
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is not None
    assert len(specification.squid_proxy.allowed_domains) == 1
    assert specification.squid_proxy.allowed_domains[0] == ".example.com"
    assert len(specification.squid_proxy.allowed_ip_addresses) == 0


def test_squid_proxy_invalid_types_in_allowed_domains() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        allowed_domains = [
            123
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_squid_proxy_empty_value_in_allowed_domains() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        allowed_domains = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_squid_proxy_missing_allowed_ip_addresses() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        allowed_domains = []
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is not None
    assert len(specification.squid_proxy.allowed_domains) == 0
    assert len(specification.squid_proxy.allowed_ip_addresses) == 0


def test_squid_proxy_empty_allowed_ip_addresses() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        allowed_ip_addresses = []
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is not None
    assert len(specification.squid_proxy.allowed_domains) == 0
    assert len(specification.squid_proxy.allowed_ip_addresses) == 0


def test_squid_proxy_populated_allowed_ip_addresses() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        allowed_ip_addresses = [
            "192.168.1.1"
        ]
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is not None
    assert len(specification.squid_proxy.allowed_domains) == 0
    assert len(specification.squid_proxy.allowed_ip_addresses) == 1
    assert specification.squid_proxy.allowed_ip_addresses[0] == "192.168.1.1"


def test_squid_proxy_invalid_types_in_allowed_ip_addresses() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        allowed_ip_addresses = [
            123
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_squid_proxy_empty_value_in_allowed_ip_addresses() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "network",
            "internet",
        ]

        [squid_proxy]
        allowed_ip_addresses = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    "domain",
    [
        pytest.param("example.com", id="registered-domain"),
        pytest.param(".example.com", id="domain-and-subdomains"),
        pytest.param("api.example.com", id="subdomain"),
        pytest.param("api-service.example.com", id="hyphenated-label"),
        pytest.param("EXAMPLE.com", id="mixed-case"),
    ],
)
def test_squid_proxy_valid_allowed_domain(domain: str) -> None:
    toml = _create_squid_proxy_toml(allowed_domains=[domain])

    specification = parse_specification(toml)

    assert specification.squid_proxy is not None
    assert specification.squid_proxy.allowed_domains == (domain,)


@pytest.mark.parametrize(
    "domain",
    [
        pytest.param(" example.com", id="leading-whitespace"),
        pytest.param("example.com ", id="trailing-whitespace"),
        pytest.param("example .com", id="embedded-whitespace"),
        pytest.param(
            "example.com\nhttp_access allow all",
            id="configuration-injection",
        ),
        pytest.param("https://example.com", id="scheme"),
        pytest.param("example.com/path", id="path"),
        pytest.param("example.com:443", id="port"),
        pytest.param("*.example.com", id="wildcard"),
        pytest.param("-example.com", id="leading-label-hyphen"),
        pytest.param("example-.com", id="trailing-label-hyphen"),
        pytest.param("example..com", id="empty-label"),
        pytest.param("example_domain.com", id="underscore"),
        pytest.param("192.0.2.1", id="ip-address"),
    ],
)
def test_squid_proxy_invalid_allowed_domain(domain: str) -> None:
    toml = _create_squid_proxy_toml(allowed_domains=[domain])

    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    "ip_address",
    [
        pytest.param("192.0.2.1", id="ipv4"),
        pytest.param("2001:db8::1", id="ipv6"),
        pytest.param("2001:DB8:0:0:0:0:0:1", id="expanded-ipv6"),
    ],
)
def test_squid_proxy_valid_allowed_ip_address(ip_address: str) -> None:
    toml = _create_squid_proxy_toml(allowed_ip_addresses=[ip_address])

    specification = parse_specification(toml)

    assert specification.squid_proxy is not None
    assert specification.squid_proxy.allowed_ip_addresses == (ip_address,)


@pytest.mark.parametrize(
    "ip_address",
    [
        pytest.param(" 192.0.2.1", id="leading-whitespace"),
        pytest.param("192.0.2.1 ", id="trailing-whitespace"),
        pytest.param(
            "192.0.2.1\nhttp_access allow all",
            id="configuration-injection",
        ),
        pytest.param("256.0.2.1", id="ipv4-octet-out-of-range"),
        pytest.param("192.0.2", id="incomplete-ipv4"),
        pytest.param("192.0.2.1/24", id="ipv4-network"),
        pytest.param("192.0.2.1:3128", id="ipv4-with-port"),
        pytest.param("https://192.0.2.1", id="scheme"),
        pytest.param("2001:db8::gggg", id="invalid-ipv6-hexadecimal"),
        pytest.param("2001:db8::1/64", id="ipv6-network"),
        pytest.param("[2001:db8::1]", id="bracketed-ipv6"),
        pytest.param("[2001:db8::1]:3128", id="ipv6-with-port"),
        pytest.param("example.com", id="domain-name"),
    ],
)
def test_squid_proxy_invalid_allowed_ip_address(ip_address: str) -> None:
    toml = _create_squid_proxy_toml(allowed_ip_addresses=[ip_address])

    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def _create_squid_proxy_toml(
    *,
    allowed_domains: list[str] | None = None,
    allowed_ip_addresses: list[str] | None = None,
) -> str:
    domain_values = allowed_domains or []
    ip_address_values = allowed_ip_addresses or []

    serialized_domains = ", ".join(json.dumps(value) for value in domain_values)
    serialized_ip_addresses = ", ".join(
        json.dumps(value) for value in ip_address_values
    )

    return f"""\
agent_name = "sample_agent"
capabilities = [
    "network",
    "internet",
]

[squid_proxy]
allowed_domains = [{serialized_domains}]
allowed_ip_addresses = [{serialized_ip_addresses}]
"""
