"""Test parsing and validation of agent_memory environment declarations."""

from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import SpecificationValidationError


def test_agent_memory_missing_environs() -> None:
    """Handle omitted environment declarations using the table's defaults."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network","postgres","agent_memory"]

        [agent_memory]
    """
    specification = parse_specification(toml)
    assert specification.agent_memory is None


def test_agent_memory_empty_environs() -> None:
    """Accept an explicitly empty environment declaration array."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network","postgres","agent_memory"]

        [agent_memory]
        environs = []
    """
    specification = parse_specification(toml)
    assert specification.agent_memory is not None
    assert specification.agent_memory.environs == frozenset()


def test_agent_memory_valid_environs() -> None:
    """Preserve literals and references separately from workload environs."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network","postgres","agent_memory"]
        environs = ["SHARED=workload"]

        [agent_memory]
        environs = [
            "SHARED=sidecar",
            "HOST_TOKEN=${host:HOST_SECRET}",
            "EMPTY=",
            "TOKEN=part1=part2",
        ]
    """
    specification = parse_specification(toml)
    assert specification.agent_memory is not None
    assert specification.agent_memory.environs == frozenset(
        {
            "SHARED=sidecar",
            "HOST_TOKEN=${host:HOST_SECRET}",
            "EMPTY=",
            "TOKEN=part1=part2",
        }
    )
    assert specification.environs == frozenset({"SHARED=workload"})


@pytest.mark.parametrize(
    "item",
    [
        "123",
        '""',
        '"   "',
        '"NAME"',
        '"1NAME=value"',
        '"PATH=value"',
        '"NAME=${vault:secret}"',
        '"NAME=${host:secret"',
    ],
)
def test_agent_memory_environs_with_invalid_item(item: str) -> None:
    """Reject invalid declarations rather than rejecting the environs field."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network","postgres","agent_memory"]

        [agent_memory]
        environs = ["VALID=value", {item}, "ALSO_VALID=value"]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "environs",
    ['"NAME=value"', '""', "123", "0", "true", "false", '{ NAME = "value" }', "{}"],
)
def test_agent_memory_not_iterable_environs(environs: str) -> None:
    """Require environment declarations to be an array."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network","postgres","agent_memory"]

        [agent_memory]
        environs = {environs}
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "environs",
    ['["NAME=value", "NAME=value"]', '["NAME=first", "NAME=second"]'],
    ids=["identical", "conflicting"],
)
def test_agent_memory_environs_reject_duplicate_keys(environs: str) -> None:
    """Reject duplicate variable names within the table's declarations."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network","postgres","agent_memory"]

        [agent_memory]
        environs = {environs}
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


def test_agent_memory_invalid_if_no_postgres_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["agent_memory","network"]

        [agent_memory]
        tools=[]        
        resources = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_agent_memory_missing_secrets() -> None:
    """Default omitted MCP secrets to an empty collection."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "agent_memory", "postgres"]

        [agent_memory]
        environs = []
    """
    specification = parse_specification(toml)
    assert specification.agent_memory is not None
    assert specification.agent_memory.secrets == frozenset()


def test_agent_memory_empty_secrets() -> None:
    """Recognize an MCP table containing only an empty secrets list."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "agent_memory", "postgres"]

        [agent_memory]
        secrets = []
    """
    specification = parse_specification(toml)
    assert specification.agent_memory is not None
    assert specification.agent_memory.secrets == frozenset()
    assert specification.agent_memory.environs == frozenset()


def test_agent_memory_only_secrets() -> None:
    """Hydrate MCP secrets without requiring tools, resources, or environs."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "agent_memory", "postgres"]

        [agent_memory]
        secrets = ["TOKEN=${host:MCP_TOKEN}"]
    """
    specification = parse_specification(toml)
    assert specification.agent_memory is not None
    assert specification.agent_memory.secrets == frozenset({"TOKEN=${host:MCP_TOKEN}"})
    assert specification.agent_memory.environs == frozenset()


def test_agent_memory_valid_secrets() -> None:
    """Preserve MCP secrets independently of other scopes and environs."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "agent_memory", "postgres"]
        secrets = ["SHARED=workload"]

        [llm_broker]
        secrets = ["SHARED=broker"]

        [agent_memory]
        environs = ["SHARED=public"]
        secrets = [
            "SHARED=mcp",
            "TOKEN=${host:HOST_SECRET}",
            "EMPTY=",
            "COMPOSITE=part1=part2",
        ]
    """
    specification = parse_specification(toml)
    assert specification.agent_memory is not None
    assert specification.agent_memory.secrets == frozenset(
        {
            "SHARED=mcp",
            "TOKEN=${host:HOST_SECRET}",
            "EMPTY=",
            "COMPOSITE=part1=part2",
        }
    )
    assert specification.agent_memory.environs == frozenset({"SHARED=public"})
    assert specification.secrets == frozenset({"SHARED=workload"})
    assert specification.llm_broker is not None
    assert specification.llm_broker.secrets == frozenset({"SHARED=broker"})


@pytest.mark.parametrize("name", ["PATH", "HTTP_PROXY", "METISA_RUNTIME_ROLE"])
def test_agent_memory_secrets_accept_reserved_names(name: str) -> None:
    """Allow secret names that are reserved for environment declarations."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "agent_memory", "postgres"]

        [agent_memory]
        secrets = ["{name}=value"]
    """
    specification = parse_specification(toml)
    assert specification.agent_memory is not None
    assert specification.agent_memory.secrets == frozenset({f"{name}=value"})


@pytest.mark.parametrize(
    "item",
    ["123", '""', '"   "', '"NAME"', '"NAME=${vault:secret}"', '"NAME=${host:secret"'],
)
def test_agent_memory_secrets_with_invalid_item(item: str) -> None:
    """Reject an invalid secret among otherwise valid MCP declarations."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "agent_memory", "postgres"]

        [agent_memory]
        secrets = ["VALID=value", {item}, "ALSO_VALID=value"]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "secrets",
    ['"NAME=value"', '""', "123", "0", "true", "false", '{ NAME = "value" }', "{}"],
)
def test_agent_memory_not_iterable_secrets(secrets: str) -> None:
    """Require MCP secret declarations to be an array."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "agent_memory", "postgres"]

        [agent_memory]
        secrets = {secrets}
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)
