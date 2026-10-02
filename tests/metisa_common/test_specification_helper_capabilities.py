from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import Capability, SpecificationValidationError


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
