"""Tests parsing and validation of workload environment declarations."""

from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import SpecificationValidationError


def test_missing_settings() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network"]
    """
    specification = parse_specification(toml)
    assert specification.settings is not None
    assert len(specification.settings.keys()) == 0


def test_empty_settings() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network"]
        settings = []
    """
    specification = parse_specification(toml)
    assert specification.settings is not None
    assert len(specification.settings.keys()) == 0


def test_invalid_settings() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network"]
        settings = [
            "invalid"
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_duplicate_keys_in_settings() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network"]
        settings = [
            "key1=value1",
            "key2=value2",
            "key1=value3",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_valid_settings() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network"]
        settings = [
            "key1=value1",
            " key2 = value2 ",
        ]
    """
    specification = parse_specification(toml)
    assert specification.settings is not None
    assert len(specification.settings.keys()) == 2
    assert specification.settings.get("key1", "") == "value1"
    assert specification.settings.get("key2", "") == "value2"
