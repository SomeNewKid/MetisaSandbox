from __future__ import annotations

import pytest

from metisa_common.models import SpecificationValidationError
from metisa_common.specification_helper import parse_specification


def test_mcp_sidecar_missing_details() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
    """
    specification = parse_specification(toml)
    assert specification.mcp_sidecar is None


def test_mcp_sidecar_with_unknown_key() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        unknown = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_sidecar_missing_tools() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        resources = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_sidecar is not None
    assert len(specification.mcp_sidecar.tools) == 0
    assert len(specification.mcp_sidecar.resources) == 0


def test_mcp_sidecar_empty_tools() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        tools = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_sidecar is not None
    assert len(specification.mcp_sidecar.tools) == 0
    assert len(specification.mcp_sidecar.resources) == 0


def test_mcp_sidecar_populated_tools() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        tools = [
            "run_script"
        ]
        resources = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_sidecar is not None
    assert len(specification.mcp_sidecar.tools) == 1
    assert specification.mcp_sidecar.tools[0] == "run_script"
    assert len(specification.mcp_sidecar.resources) == 0


def test_mcp_sidecar_invalid_types_in_tools() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        tools = [
            123
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_sidecar_empty_value_in_tools() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        tools = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_sidecar_missing_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        tools = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_sidecar is not None
    assert len(specification.mcp_sidecar.tools) == 0
    assert len(specification.mcp_sidecar.resources) == 0


def test_mcp_sidecar_empty_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        resources = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_sidecar is not None
    assert len(specification.mcp_sidecar.tools) == 0
    assert len(specification.mcp_sidecar.resources) == 0


def test_mcp_sidecar_populated_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        resources = [
            "refund_policy"
        ]
    """
    specification = parse_specification(toml)
    assert specification.mcp_sidecar is not None
    assert len(specification.mcp_sidecar.tools) == 0
    assert len(specification.mcp_sidecar.resources) == 1
    assert specification.mcp_sidecar.resources[0] == "refund_policy"


def test_mcp_sidecar_invalid_types_in_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        resources = [
            123
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_sidecar_empty_value_in_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        resources = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_sidecar_whitespace_value_in_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [mcp_sidecar]
        resources = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)
