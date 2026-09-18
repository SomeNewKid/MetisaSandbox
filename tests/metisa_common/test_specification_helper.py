from __future__ import annotations

import pytest

from metisa_common.models import Capability, SpecificationValidationError
from metisa_common.specification_helper import parse_specification


def test_empty_toml_file() -> None:
    toml = ""
    with pytest.raises(ValueError):
        _ = parse_specification(toml)


def test_missing_agent_name() -> None:
    toml = """
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_invalid_type_agent_name() -> None:
    toml = """
        agent_name = 123
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_empty_agent_name() -> None:
    toml = """
        agent_name = ""
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_whitespace_agent_name() -> None:
    toml = """
        agent_name = "  "
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_minimal_toml_file() -> None:
    toml = """
        agent_name="sample_agent"
    """
    specification = parse_specification(toml)
    assert specification.agent_name == "sample_agent"


def test_minimal_toml_file_with_whitespaced_value() -> None:
    toml = """
        agent_name="  sample_agent  "
    """
    specification = parse_specification(toml)
    assert specification.agent_name == "sample_agent"


def test_not_iterable_capabilities() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = "network"
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_empty_capabilities() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []
    """
    specification = parse_specification(toml)
    assert len(specification.capabilities) == 0


def test_capabilities_with_an_invalid_type() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [123]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_capabilities_with_unsupported_value() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["unsupported_capability"]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_valid_capabilities() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network"]
    """
    specification = parse_specification(toml)
    assert len(specification.capabilities) == 1
    assert Capability.NETWORK in specification.capabilities


def test_specification_with_unknown_key() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []
        unknown = "value"
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_specification_with_unknown_table() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [unknown_table]
        unknown = "value"
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)
