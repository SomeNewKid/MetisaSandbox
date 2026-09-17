from __future__ import annotations

import pytest

from metisa_common.models import Capability, SpecificationValidationError
from metisa_common.specification_helper import parse_specification


def test_empty_toml_file() -> None:
    toml = ""
    with pytest.raises(ValueError):
        _ = parse_specification(toml)


def test_missing_schema_version() -> None:
    toml = """
        workload_name="sample_agent"
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_invalid_schema_version_if_string() -> None:
    toml = """
        schema_version = "1"
        workload_name="sample_agent"
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_invalid_schema_version_if_bool() -> None:
    # a bool will pass an `isinstance(value, int)` check
    toml = """
        schema_version = true
        workload_name="sample_agent"
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_missing_workload_name() -> None:
    toml = """
        schema_version = 1
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_invalid_type_workload_name() -> None:
    toml = """
        schema_version = 1
        workload_name = 123
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_empty_workload_name() -> None:
    toml = """
        schema_version = 1
        workload_name = ""
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_whitespace_workload_name() -> None:
    toml = """
        schema_version = 1
        workload_name = "  "
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_minimal_toml_file() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
    """
    specification = parse_specification(toml)
    assert specification.schema_version == 1
    assert specification.workload_name == "sample_agent"


def test_minimal_toml_file_with_whitespaced_value() -> None:
    toml = """
        schema_version = 1
        workload_name="  sample_agent  "
    """
    specification = parse_specification(toml)
    assert specification.schema_version == 1
    assert specification.workload_name == "sample_agent"


def test_not_iterable_capabilities() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = "network"
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_empty_capabilities() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []
    """
    specification = parse_specification(toml)
    assert len(specification.capabilities) == 0


def test_capabilities_with_an_invalid_type() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = [123]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_capabilities_with_unsupported_value() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = ["unsupported_capability"]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_valid_capabilities() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = ["network"]
    """
    specification = parse_specification(toml)
    assert len(specification.capabilities) == 1
    assert Capability.NETWORK in specification.capabilities


def test_specification_with_unknown_key() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []
        unknown = "value"
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_specification_with_unknown_table() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [unknown_table]
        unknown = "value"
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)
