"""Test code execution capability and environment declarations."""

from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import SpecificationValidationError


def test_missing_code_execution_table() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "code_execution"]
    """
    specification = parse_specification(toml)
    assert specification.code_execution is None


def test_code_execution_missing_environs() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "code_execution"]

        [code_execution]
    """
    specification = parse_specification(toml)
    assert specification.code_execution is None


def test_code_execution_invalid_if_no_network_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["mcp_server", "code_execution"]

        [code_execution]
        environs = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_code_execution_invalid_if_no_mcp_server_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "code_execution"]

        [code_execution]
        environs = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_code_execution_invalid_if_no_code_execution_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server"]

        [code_execution]
        environs = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize("key", ["unknown", "tools", "resources"])
def test_code_execution_with_unknown_key(key: str) -> None:
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "code_execution"]

        [code_execution]
        {key} = []
    """
    with pytest.raises(SpecificationValidationError, match="unknown keys"):
        _ = parse_specification(toml)


def test_code_execution_empty_environs() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "code_execution"]

        [code_execution]
        environs = []
    """
    specification = parse_specification(toml)
    assert specification.code_execution is not None
    assert specification.code_execution.environs == frozenset()


def test_code_execution_valid_environs() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "code_execution"]
        environs = ["WORKLOAD=value"]

        [mcp_server]
        environs = ["MCP=value"]

        [code_execution]
        environs = [
            "LITERAL=hard-coded value",
            "CODE_EXECUTION_API_KEY=${host:CODE_EXECUTION_API_KEY}",
            "EMPTY=",
            "TOKEN=part1=part2",
        ]
    """
    specification = parse_specification(toml)
    assert specification.code_execution is not None
    assert specification.code_execution.environs == frozenset(
        {
            "LITERAL=hard-coded value",
            "CODE_EXECUTION_API_KEY=${host:CODE_EXECUTION_API_KEY}",
            "EMPTY=",
            "TOKEN=part1=part2",
        }
    )
    assert specification.environs == frozenset({"WORKLOAD=value"})
    assert specification.mcp_server is not None
    assert specification.mcp_server.environs == frozenset({"MCP=value"})


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
def test_code_execution_environs_with_invalid_item(item: str) -> None:
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "code_execution"]

        [code_execution]
        environs = ["VALID=value", {item}, "ALSO_VALID=value"]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)
