from __future__ import annotations

import pytest

from metisa_common.models import SpecificationValidationError
from metisa_common.specification_helper import parse_specification


def test_haproxy_missing_details() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [haproxy]
    """
    specification = parse_specification(toml)
    assert specification.haproxy is None


def test_haproxy_unknown_key() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [haproxy]
        unknown = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_haproxy_empty_ports() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [haproxy]
        ports = []
    """
    specification = parse_specification(toml)
    assert specification.haproxy is not None
    assert len(specification.haproxy.ports) == 0


def test_haproxy_populated_ports() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [haproxy]
        ports = [
            3306
        ]
    """
    specification = parse_specification(toml)
    assert specification.haproxy is not None
    assert len(specification.haproxy.ports) == 1
    assert specification.haproxy.ports[0] == 3306


def test_haproxy_invalid_types_in_ports() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [haproxy]
        ports = [
            "3306"
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_haproxy_invalid_value_in_ports() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [haproxy]
        ports = [
            -3306
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)
