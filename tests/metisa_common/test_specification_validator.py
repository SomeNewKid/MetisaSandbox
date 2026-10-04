from __future__ import annotations

import pytest

from metisa_common.specification_validator import (
    is_valid_domain_name,
    is_valid_ipv4_address,
    is_valid_ipv6_address,
)


@pytest.mark.parametrize(
    ("value", "suffix_domain_ok"),
    [
        pytest.param("example.com", False, id="registered-domain"),
        pytest.param("a.example.com", False, id="one-character subdomain"),
        pytest.param("ai.example.com", False, id="two-character subdomain"),
        pytest.param("api.example.com", False, id="three-character subdomain"),
        pytest.param("apis.example.com", False, id="four-character subdomain"),
        pytest.param("api-service.example.com", False, id="hyphenated-label"),
        pytest.param("api2.example.com", False, id="alphanumeric-label"),
        pytest.param("EXAMPLE.com", False, id="mixed-case"),
        pytest.param("xn--bcher-kva.example", False, id="punycode-label"),
        pytest.param(".example.com", True, id="suffix-domain"),
        pytest.param("example.com", True, id="regular-domain-with-suffix-enabled"),
    ],
)
def test_is_valid_domain_name_happy_path(
    value: str,
    suffix_domain_ok: bool,
) -> None:
    assert is_valid_domain_name(value, suffix_domain_ok=suffix_domain_ok) is True


@pytest.mark.parametrize(
    ("value", "suffix_domain_ok"),
    [
        pytest.param("", False, id="empty"),
        pytest.param("   ", False, id="whitespace-only"),
        pytest.param(" example.com", False, id="leading-whitespace"),
        pytest.param("example.com ", False, id="trailing-whitespace"),
        pytest.param("example .com", False, id="embedded-whitespace"),
        pytest.param("example.com\nhttp_access allow all", False, id="newline"),
        pytest.param("https://example.com", False, id="scheme"),
        pytest.param("example.com/path", False, id="path"),
        pytest.param("example.com:443", False, id="port"),
        pytest.param("*.example.com", False, id="wildcard"),
        pytest.param("_service.example.com", False, id="leading_underscore"),
        pytest.param("example_domain.com", False, id="underscore"),
        pytest.param("-example.com", False, id="leading-hyphen"),
        pytest.param("example-.com", False, id="trailing-hyphen"),
        pytest.param("example..com", False, id="empty-label"),
        pytest.param(".example.com", False, id="suffix-not-enabled"),
        pytest.param("..example.com", True, id="empty-suffix-label"),
        pytest.param("192.0.2.1", False, id="ip-address"),
        pytest.param(f"{'a' * 64}.example.com", False, id="label-too-long"),
    ],
)
def test_is_valid_domain_name_unhappy_path(
    value: str,
    suffix_domain_ok: bool,
) -> None:
    assert is_valid_domain_name(value, suffix_domain_ok=suffix_domain_ok) is False


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("0.0.0.0", id="unspecified"),
        pytest.param("127.0.0.1", id="loopback"),
        pytest.param("192.0.2.1", id="documentation-address"),
        pytest.param("255.255.255.255", id="maximum-address"),
    ],
)
def test_is_valid_ipv4_address_happy_path(value: str) -> None:
    assert is_valid_ipv4_address(value) is True


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace-only"),
        pytest.param(" 192.0.2.1", id="leading-whitespace"),
        pytest.param("192.0.2.1 ", id="trailing-whitespace"),
        pytest.param("192.0.2.1\nhttp_access allow all", id="newline"),
        pytest.param("256.0.2.1", id="octet-too-large"),
        pytest.param("192.0.2", id="too-few-octets"),
        pytest.param("192.0.2.1.5", id="too-many-octets"),
        pytest.param("192.168.001.1", id="leading-zero"),
        pytest.param("-1.0.0.1", id="negative-octet"),
        pytest.param("192.0.2.1/24", id="network-prefix"),
        pytest.param("192.0.2.1:3128", id="port"),
        pytest.param("https://192.0.2.1", id="scheme"),
        pytest.param("example.com", id="domain-name"),
        pytest.param("2001:db8::1", id="ipv6-address"),
    ],
)
def test_is_valid_ipv4_address_unhappy_path(value: str) -> None:
    assert is_valid_ipv4_address(value) is False


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("::", id="unspecified"),
        pytest.param("::1", id="loopback"),
        pytest.param("2001:db8::1", id="compressed"),
        pytest.param("2001:DB8:0:0:0:0:0:1", id="expanded-mixed-case"),
        pytest.param("::ffff:192.0.2.128", id="ipv4-mapped"),
    ],
)
def test_is_valid_ipv6_address_happy_path(value: str) -> None:
    assert is_valid_ipv6_address(value) is True


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace-only"),
        pytest.param(" 2001:db8::1", id="leading-whitespace"),
        pytest.param("2001:db8::1 ", id="trailing-whitespace"),
        pytest.param("2001:db8::1\nhttp_access allow all", id="newline"),
        pytest.param("2001:db8::gggg", id="non-hexadecimal-group"),
        pytest.param("2001:db8::12345", id="group-too-long"),
        pytest.param("2001:db8::1::2", id="multiple-compression-markers"),
        pytest.param("2001:db8:0:0:0:0:1", id="too-few-groups"),
        pytest.param("2001:db8:0:0:0:0:0:1:2", id="too-many-groups"),
        pytest.param("2001:db8::1/64", id="network-prefix"),
        pytest.param("[2001:db8::1]", id="brackets"),
        pytest.param("[2001:db8::1]:3128", id="port"),
        pytest.param("fe80::1%eth0", id="zone-identifier"),
        pytest.param("example.com", id="domain-name"),
        pytest.param("192.0.2.1", id="ipv4-address"),
    ],
)
def test_is_valid_ipv6_address_unhappy_path(value: str) -> None:
    assert is_valid_ipv6_address(value) is False
