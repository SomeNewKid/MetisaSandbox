from __future__ import annotations

import pytest

from metisa_common.models import SpecificationValidationError
from metisa_common.specification_helper import parse_specification


def test_squid_proxy_missing_details() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [squid_proxy]
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is None


def test_squid_proxy_with_unknown_key() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [squid_proxy]
        unknown = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_squid_proxy_missing_allowed_domains() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [squid_proxy]
        allowed_ip_addresses = []
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is not None
    assert len(specification.squid_proxy.allowed_domains) == 0
    assert len(specification.squid_proxy.allowed_ip_addresses) == 0


def test_squid_proxy_empty_allowed_domains() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [squid_proxy]
        allowed_domains = []
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is not None
    assert len(specification.squid_proxy.allowed_domains) == 0
    assert len(specification.squid_proxy.allowed_ip_addresses) == 0


def test_squid_proxy_populated_allowed_domains() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

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
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [squid_proxy]
        allowed_domains = [
            123
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_squid_proxy_empty_value_in_allowed_domains() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [squid_proxy]
        allowed_domains = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_squid_proxy_missing_allowed_ip_addresses() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [squid_proxy]
        allowed_domains = []
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is not None
    assert len(specification.squid_proxy.allowed_domains) == 0
    assert len(specification.squid_proxy.allowed_ip_addresses) == 0


def test_squid_proxy_empty_allowed_ip_addresses() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [squid_proxy]
        allowed_ip_addresses = []
    """
    specification = parse_specification(toml)
    assert specification.squid_proxy is not None
    assert len(specification.squid_proxy.allowed_domains) == 0
    assert len(specification.squid_proxy.allowed_ip_addresses) == 0


def test_squid_proxy_populated_allowed_ip_addresses() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

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
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [squid_proxy]
        allowed_ip_addresses = [
            123
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_squid_proxy_empty_value_in_allowed_ip_addresses() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [squid_proxy]
        allowed_ip_addresses = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)
