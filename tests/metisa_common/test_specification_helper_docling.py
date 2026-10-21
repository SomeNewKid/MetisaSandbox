"""Test Docling capability and environment declarations."""

from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import SpecificationValidationError


def test_missing_docling_table() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "mcp_server", 
            "prompt_guard",
            "entity_guard", 
            "documents",
            "docling"
        ]
    """
    specification = parse_specification(toml)
    assert specification.docling is None


def test_docling_missing_environs_and_embedding_model() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "mcp_server", 
            "prompt_guard", 
            "entity_guard", 
            "documents",
            "docling"
        ]

        [docling]
    """
    specification = parse_specification(toml)
    assert specification.docling is None


def test_docling_invalid_if_no_network_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = ["mcp_server", "prompt_guard", "entity_guard", "docling"]

        [docling]
        environs = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_docling_invalid_if_no_mcp_server_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "prompt_guard", 
            "entity_guard", 
            "documents",
            "docling",
        ]

        [docling]
        environs = []
        embedding_model = "BAAI/bge-small-en-v1.5"        
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_docling_invalid_if_no_documents_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "mcp_server",
            "prompt_guard", 
            "entity_guard", 
            "docling",
        ]

        [docling]
        environs = []
        embedding_model = "BAAI/bge-small-en-v1.5"        
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_docling_valid_if_no_docling_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "mcp_server",
            "prompt_guard", 
            "entity_guard",
            "documents",
        ]

        [docling]
        environs = []
        embedding_model = "BAAI/bge-small-en-v1.5" 
    """
    specification = parse_specification(toml)
    assert specification.docling is not None
    assert specification.docling.embedding_model == "BAAI/bge-small-en-v1.5"


def test_docling_invalid_if_empty_embedding_model() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "mcp_server",
            "prompt_guard", 
            "entity_guard",
            "documents",
        ]

        [docling]
        environs = []
        embedding_model = "" 
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_docling_invalid_if_non_string_embedding_model() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "mcp_server",
            "prompt_guard", 
            "entity_guard",
            "documents",
            "docling",
        ]

        [docling]
        environs = []
        embedding_model = 123 
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize("key", ["unknown", "tools", "resources"])
def test_docling_with_unknown_key(key: str) -> None:
    toml = f"""
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "mcp_server",
            "prompt_guard", 
            "entity_guard",
            "documents",
            "docling",
        ]

        [docling]
        {key} = []
    """
    with pytest.raises(SpecificationValidationError, match="unknown keys"):
        _ = parse_specification(toml)


def test_docling_empty_environs() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "mcp_server",
            "prompt_guard", 
            "entity_guard",
            "documents",
            "docling",
        ]

        [docling]
        environs = []
        embedding_model = "BAAI/bge-small-en-v1.5"
    """
    specification = parse_specification(toml)
    assert specification.docling is not None
    assert specification.docling.environs == frozenset()


def test_docling_valid_environs() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "mcp_server",
            "prompt_guard", 
            "entity_guard",
            "documents",
            "docling",
        ]
        environs = ["WORKLOAD=value"]

        [mcp_server]
        environs = ["MCP=value"]

        [docling]
        environs = [
            "LITERAL=hard-coded value",
            "JINA_API_KEY=${host:JINA_API_KEY}",
            "EMPTY=",
            "TOKEN=part1=part2",
        ]
        embedding_model = "BAAI/bge-small-en-v1.5"
    """
    specification = parse_specification(toml)
    assert specification.docling is not None
    assert specification.docling.environs == frozenset(
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
def test_docling_environs_with_invalid_item(item: str) -> None:
    toml = f"""
        agent_name = "sample_agent"
        capabilities = [
            "network", 
            "mcp_server",
            "prompt_guard", 
            "entity_guard",
            "documents",
            "docling",
        ]

        [docling]
        environs = ["VALID=value", {item}, "ALSO_VALID=value"]
        embedding_model = "BAAI/bge-small-en-v1.5"
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)
