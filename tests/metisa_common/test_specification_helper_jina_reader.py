"""Test Jina Reader capability and environment declarations."""

from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import SpecificationValidationError


def test_missing_jina_reader_table() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "prompt_guard", "jina_reader"]
    """
    specification = parse_specification(toml)
    assert specification.jina_reader is None


def test_jina_reader_missing_environs() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "prompt_guard", "jina_reader"]

        [jina_reader]
    """
    specification = parse_specification(toml)
    assert specification.jina_reader is None


def test_jina_reader_invalid_if_no_network_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["mcp_server", "prompt_guard", "jina_reader"]

        [jina_reader]
        environs = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_jina_reader_invalid_if_no_mcp_server_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "prompt_guard", "jina_reader"]

        [jina_reader]
        environs = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_jina_reader_invalid_if_no_jina_reader_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "prompt_guard"]

        [jina_reader]
        environs = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize("key", ["unknown", "tools", "resources"])
def test_jina_reader_with_unknown_key(key: str) -> None:
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "prompt_guard", "jina_reader"]

        [jina_reader]
        {key} = []
    """
    with pytest.raises(SpecificationValidationError, match="unknown keys"):
        _ = parse_specification(toml)


def test_jina_reader_empty_environs() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "prompt_guard", "jina_reader"]

        [jina_reader]
        environs = []
    """
    specification = parse_specification(toml)
    assert specification.jina_reader is not None
    assert specification.jina_reader.environs == frozenset()


def test_jina_reader_valid_environs() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "prompt_guard", "jina_reader"]
        environs = ["WORKLOAD=value"]

        [mcp_server]
        environs = ["MCP=value"]

        [jina_reader]
        environs = [
            "LITERAL=hard-coded value",
            "JINA_API_KEY=${host:JINA_API_KEY}",
            "EMPTY=",
            "TOKEN=part1=part2",
        ]
    """
    specification = parse_specification(toml)
    assert specification.jina_reader is not None
    assert specification.jina_reader.environs == frozenset(
        {
            "LITERAL=hard-coded value",
            "JINA_API_KEY=${host:JINA_API_KEY}",
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
def test_jina_reader_environs_with_invalid_item(item: str) -> None:
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "mcp_server", "prompt_guard", "jina_reader"]

        [jina_reader]
        environs = ["VALID=value", {item}, "ALSO_VALID=value"]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)
