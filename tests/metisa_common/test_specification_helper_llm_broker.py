"""Test LLM Broker capability and environment declarations."""

from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import Capability, SpecificationValidationError


def test_missing_llm_broker_table() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "llm_broker", "prompt_guard", "entity_guard"]
    """
    specification = parse_specification(toml)
    assert Capability.LLM_BROKER in specification.capabilities
    assert specification.llm_broker is None


def test_llm_broker_missing_environs() -> None:
    """Treat a table without environment declarations as absent."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "llm_broker", "prompt_guard", "entity_guard"]

        [llm_broker]
    """
    specification = parse_specification(toml)
    assert specification.llm_broker is None


def test_llm_broker_invalid_if_no_network_capability() -> None:
    """Reject the capability even when no broker table is supplied."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["llm_broker", "prompt_guard", "entity_guard"]
    """
    with pytest.raises(SpecificationValidationError, match="requires.*network"):
        _ = parse_specification(toml)


def test_llm_broker_invalid_if_no_prompt_guard_capability() -> None:
    """Reject the capability even when no broker table is supplied."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "llm_broker"]
    """
    with pytest.raises(SpecificationValidationError, match="requires.*prompt_guard"):
        _ = parse_specification(toml)


def test_llm_broker_valid_if_no_llm_broker_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "prompt_guard", "entity_guard"]

        [llm_broker]
        environs = []
    """
    specification = parse_specification(toml)
    assert specification.llm_broker is not None


@pytest.mark.parametrize("key", ["unknown", "tools", "resources"])
def test_llm_broker_with_unknown_key(key: str) -> None:
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "llm_broker", "prompt_guard", "entity_guard"]

        [llm_broker]
        {key} = []
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert f"unknown keys: {key}" in str(error.value)


def test_llm_broker_empty_environs() -> None:
    """Accept empty broker environs without requiring the MCP capability."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "llm_broker", "prompt_guard", "entity_guard"]

        [llm_broker]
        environs = []
    """
    specification = parse_specification(toml)
    assert specification.llm_broker is not None
    assert specification.llm_broker.environs == frozenset()
    assert specification.mcp_server is None


def test_llm_broker_valid_environs() -> None:
    """Preserve broker literals and references separately from other environs."""
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "llm_broker", 
            "mcp_server", 
            "prompt_guard", 
            "entity_guard"
        ]
        environs = ["WORKLOAD=value"]

        [mcp_server]
        environs = ["MCP=value"]

        [llm_broker]
        environs = [
            "LITERAL=hard-coded value",
            "SECRET=${host:HOST_SECRET}",
            "EMPTY=",
            "TOKEN=part1=part2",
        ]
    """
    specification = parse_specification(toml)
    assert specification.llm_broker is not None
    assert specification.llm_broker.environs == frozenset(
        {
            "LITERAL=hard-coded value",
            "SECRET=${host:HOST_SECRET}",
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
def test_llm_broker_environs_with_invalid_item(item: str) -> None:
    """Reject invalid items among otherwise valid environment declarations."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "llm_broker", "prompt_guard", "entity_guard"]

        [llm_broker]
        environs = ["VALID=value", {item}, "ALSO_VALID=value"]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "environs",
    ['"NAME=value"', '""', "123", "0", "true", "false", '{ NAME = "value" }', "{}"],
)
def test_llm_broker_not_iterable_environs(environs: str) -> None:
    """Require the environment declarations field to be an array."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "llm_broker", "prompt_guard", "entity_guard"]

        [llm_broker]
        environs = {environs}
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)
