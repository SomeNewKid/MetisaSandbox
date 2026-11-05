from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import Capability, SpecificationValidationError


def test_interactive_invalid_if_no_network_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["interactive", "mcp_server", "prompt_guard", "entity_guard"]

        [mcp_server]
        tools=[]        
        resources = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_interactive_invalid_if_no_mcp_server_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "interactive", "prompt_guard", "entity_guard"]

        [mcp_server]
        tools=[]        
        resources = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_interactive_invalid_if_no_prompt_guard_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["interactive", "mcp_server", "network", "entity_guard"]

        [mcp_server]
        tools=[]        
        resources = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_interactive_invalid_if_no_entity_guard_capability() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = ["interactive", "mcp_server", "network", "prompt_guard"]

        [mcp_server]
        tools=[]        
        resources = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_interactive_valid_if_has_required_capabilities() -> None:
    toml = """
        agent_name="sample_agent"
        capabilities = [
            "interactive", "mcp_server", "network", "prompt_guard", "entity_guard"
        ]

        [mcp_server]
        tools=[]        
        resources = []
    """
    specification = parse_specification(toml)
    assert Capability.INTERACTIVE in specification.capabilities
