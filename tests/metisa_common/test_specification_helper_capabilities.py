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


def test_network_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network"]
    """
    specification = parse_specification(toml)
    assert Capability.NETWORK in specification.capabilities
    assert Capability.INTERNET not in specification.capabilities
    assert Capability.LOCALNET not in specification.capabilities
    assert Capability.MCP_SERVER not in specification.capabilities
    assert Capability.JINA_READER not in specification.capabilities
    assert Capability.CODE_EXECUTION not in specification.capabilities
    assert Capability.LLM_SERVER not in specification.capabilities
    assert Capability.PROMPT_GUARD not in specification.capabilities
    assert Capability.PLAYWRIGHT_CHROMIUM not in specification.capabilities
    assert Capability.OPENAI not in specification.capabilities


def test_internet_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "internet"]
    """
    specification = parse_specification(toml)
    assert Capability.NETWORK in specification.capabilities
    assert Capability.INTERNET in specification.capabilities
    assert Capability.LOCALNET not in specification.capabilities
    assert Capability.MCP_SERVER not in specification.capabilities
    assert Capability.JINA_READER not in specification.capabilities
    assert Capability.CODE_EXECUTION not in specification.capabilities
    assert Capability.LLM_SERVER not in specification.capabilities
    assert Capability.PROMPT_GUARD not in specification.capabilities
    assert Capability.PLAYWRIGHT_CHROMIUM not in specification.capabilities
    assert Capability.OPENAI not in specification.capabilities


def test_localnet_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "localnet"]
    """
    specification = parse_specification(toml)
    assert Capability.NETWORK in specification.capabilities
    assert Capability.INTERNET not in specification.capabilities
    assert Capability.LOCALNET in specification.capabilities
    assert Capability.MCP_SERVER not in specification.capabilities
    assert Capability.JINA_READER not in specification.capabilities
    assert Capability.CODE_EXECUTION not in specification.capabilities
    assert Capability.LLM_SERVER not in specification.capabilities
    assert Capability.PROMPT_GUARD not in specification.capabilities
    assert Capability.PLAYWRIGHT_CHROMIUM not in specification.capabilities
    assert Capability.OPENAI not in specification.capabilities


def test_mcp_server_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_server", "prompt_guard"]
    """
    specification = parse_specification(toml)
    assert Capability.NETWORK in specification.capabilities
    assert Capability.INTERNET not in specification.capabilities
    assert Capability.LOCALNET not in specification.capabilities
    assert Capability.MCP_SERVER in specification.capabilities
    assert Capability.JINA_READER not in specification.capabilities
    assert Capability.CODE_EXECUTION not in specification.capabilities
    assert Capability.LLM_SERVER not in specification.capabilities
    assert Capability.PROMPT_GUARD in specification.capabilities
    assert Capability.PLAYWRIGHT_CHROMIUM not in specification.capabilities
    assert Capability.OPENAI not in specification.capabilities


def test_jina_reader_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_server", "prompt_guard", "jina_reader"]
    """
    specification = parse_specification(toml)
    assert Capability.NETWORK in specification.capabilities
    assert Capability.INTERNET not in specification.capabilities
    assert Capability.LOCALNET not in specification.capabilities
    assert Capability.MCP_SERVER in specification.capabilities
    assert Capability.JINA_READER in specification.capabilities
    assert Capability.CODE_EXECUTION not in specification.capabilities
    assert Capability.LLM_SERVER not in specification.capabilities
    assert Capability.PROMPT_GUARD in specification.capabilities
    assert Capability.PLAYWRIGHT_CHROMIUM not in specification.capabilities
    assert Capability.OPENAI not in specification.capabilities


def test_code_execution_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "mcp_server", "prompt_guard", "code_execution"]
    """
    specification = parse_specification(toml)
    assert Capability.NETWORK in specification.capabilities
    assert Capability.INTERNET not in specification.capabilities
    assert Capability.LOCALNET not in specification.capabilities
    assert Capability.MCP_SERVER in specification.capabilities
    assert Capability.JINA_READER not in specification.capabilities
    assert Capability.CODE_EXECUTION in specification.capabilities
    assert Capability.LLM_SERVER not in specification.capabilities
    assert Capability.PROMPT_GUARD in specification.capabilities
    assert Capability.PLAYWRIGHT_CHROMIUM not in specification.capabilities
    assert Capability.OPENAI not in specification.capabilities


def test_llm_server_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["llm_server", "network"]
    """
    specification = parse_specification(toml)
    assert Capability.NETWORK in specification.capabilities
    assert Capability.INTERNET not in specification.capabilities
    assert Capability.LOCALNET not in specification.capabilities
    assert Capability.MCP_SERVER not in specification.capabilities
    assert Capability.JINA_READER not in specification.capabilities
    assert Capability.CODE_EXECUTION not in specification.capabilities
    assert Capability.LLM_SERVER in specification.capabilities
    assert Capability.PROMPT_GUARD not in specification.capabilities
    assert Capability.PLAYWRIGHT_CHROMIUM not in specification.capabilities
    assert Capability.OPENAI not in specification.capabilities


def test_prompt_guard_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["prompt_guard"]
    """
    specification = parse_specification(toml)
    assert Capability.NETWORK not in specification.capabilities
    assert Capability.INTERNET not in specification.capabilities
    assert Capability.LOCALNET not in specification.capabilities
    assert Capability.MCP_SERVER not in specification.capabilities
    assert Capability.JINA_READER not in specification.capabilities
    assert Capability.CODE_EXECUTION not in specification.capabilities
    assert Capability.LLM_SERVER not in specification.capabilities
    assert Capability.PROMPT_GUARD in specification.capabilities
    assert Capability.PLAYWRIGHT_CHROMIUM not in specification.capabilities
    assert Capability.OPENAI not in specification.capabilities


def test_playwright_chromium_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["playwright_chromium"]
    """
    specification = parse_specification(toml)
    assert Capability.NETWORK not in specification.capabilities
    assert Capability.INTERNET not in specification.capabilities
    assert Capability.LOCALNET not in specification.capabilities
    assert Capability.MCP_SERVER not in specification.capabilities
    assert Capability.JINA_READER not in specification.capabilities
    assert Capability.CODE_EXECUTION not in specification.capabilities
    assert Capability.LLM_SERVER not in specification.capabilities
    assert Capability.PROMPT_GUARD not in specification.capabilities
    assert Capability.PLAYWRIGHT_CHROMIUM in specification.capabilities
    assert Capability.OPENAI not in specification.capabilities


def test_openai_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["openai"]
    """
    specification = parse_specification(toml)
    assert Capability.NETWORK not in specification.capabilities
    assert Capability.INTERNET not in specification.capabilities
    assert Capability.LOCALNET not in specification.capabilities
    assert Capability.MCP_SERVER not in specification.capabilities
    assert Capability.JINA_READER not in specification.capabilities
    assert Capability.CODE_EXECUTION not in specification.capabilities
    assert Capability.LLM_SERVER not in specification.capabilities
    assert Capability.PROMPT_GUARD not in specification.capabilities
    assert Capability.PLAYWRIGHT_CHROMIUM not in specification.capabilities
    assert Capability.OPENAI in specification.capabilities


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
