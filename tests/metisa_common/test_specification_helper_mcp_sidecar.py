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


def test_mcp_server_missing_environs() -> None:
    """Default omitted MCP environment declarations to an empty collection."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        tools = []
        resources = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is not None
    assert specification.mcp_server.environs == frozenset()


def test_mcp_server_empty_environs() -> None:
    """Accept an explicitly empty MCP environment declaration list."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        tools = []
        resources = []
        environs = []
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is not None
    assert specification.mcp_server.environs == frozenset()


def test_mcp_server_valid_environs() -> None:
    """Preserve MCP literals and host references separately from workload environs."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_client"]
        environs = ["WORKLOAD=value"]

        [mcp_server]
        tools = []
        resources = []
        environs = [
            "LITERAL=hard-coded value",
            "SECRET=${host:HOST_SECRET}",
            "EMPTY=",
            "TOKEN=part1=part2",
        ]
    """
    specification = parse_specification(toml)
    assert specification.mcp_server is not None
    assert specification.mcp_server.environs == frozenset(
        {
            "LITERAL=hard-coded value",
            "SECRET=${host:HOST_SECRET}",
            "EMPTY=",
            "TOKEN=part1=part2",
        }
    )
    assert specification.environs == frozenset({"WORKLOAD=value"})


@pytest.mark.parametrize(
    "item",
    [
        "123",
        '""',
        '"   "',
        '"NAME"',
        '"NAME=${vault:secret}"',
        '"NAME=${host:secret"',
    ],
)
def test_mcp_server_environs_with_invalid_item(item: str) -> None:
    """Reject a list containing an invalid item among valid declarations."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_client"]

        [mcp_server]
        tools = []
        resources = []
        environs = ["VALID=value", {item}, "ALSO_VALID=value"]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)
