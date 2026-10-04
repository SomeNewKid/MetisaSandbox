from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import SpecificationValidationError


def test_missing_mcp_server_table() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is None


def test_mcp_server_missing_details() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is None


def test_mcp_server_invalid_if_no_network_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["mcp_client"]

        [mcp_server]
        tools=[]        
        resources = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_server_invalid_if_no_mcp_client_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network"]

        [mcp_server]
        tools=[]        
        resources = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_server_with_unknown_key() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        unknown = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_server_missing_tools() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        resources = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is not None
    assert len(specification.mcp_server.tools) == 0
    assert len(specification.mcp_server.resources) == 0


def test_mcp_server_empty_tools() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        tools = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is not None
    assert len(specification.mcp_server.tools) == 0
    assert len(specification.mcp_server.resources) == 0


def test_mcp_server_populated_tools() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        tools = [
            "run_script"
        ]
        resources = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is not None
    assert len(specification.mcp_server.tools) == 1
    assert specification.mcp_server.tools[0] == "run_script"
    assert len(specification.mcp_server.resources) == 0


def test_mcp_server_invalid_types_in_tools() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        tools = [
            123
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_server_empty_value_in_tools() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        tools = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_server_missing_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        tools = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is not None
    assert len(specification.mcp_server.tools) == 0
    assert len(specification.mcp_server.resources) == 0


def test_mcp_server_empty_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        resources = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is not None
    assert len(specification.mcp_server.tools) == 0
    assert len(specification.mcp_server.resources) == 0


def test_mcp_server_populated_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        resources = [
            "refund_policy"
        ]
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is not None
    assert len(specification.mcp_server.tools) == 0
    assert len(specification.mcp_server.resources) == 1
    assert specification.mcp_server.resources[0] == "refund_policy"


def test_mcp_server_invalid_types_in_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        resources = [
            123
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_server_empty_value_in_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        resources = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_mcp_server_whitespace_value_in_resources() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        resources = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)
