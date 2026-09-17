"""
Provides the models to represent the Metisa TOML specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique


@unique
class Capability(StrEnum):
    INTERACTIVE = "interactive"
    NETWORK = "network"
    MCP_CLIENT = "mcp_client"
    OPENAI_AGENTS = "openai_agents"
    JINA_READER = "jina_reader"
    CODE_EXECUTION = "code_execution"
    HAPROXY = "haproxy"
    OLLAMA = "ollama"
    PLAYWRIGHT_CHROMIUM = "playwright_chromium"


class SpecificationValidationError(ValueError):
    """Indicates that a parsed specification violates the Metisa schema."""


@dataclass(frozen=True)
class MetisaSpecification:
    schema_version: int
    workload_name: str
    capabilities: frozenset[Capability]
    haproxy: HaproxySpecification | None
    squid_proxy: SquidProxySpecification | None
    ollama_sidecar: OllamaSidecarSpecification | None
    mcp_sidecar: McpSidecarSpecification | None


@dataclass(frozen=True)
class HaproxySpecification:
    ports: tuple[int, ...]


@dataclass(frozen=True)
class SquidProxySpecification:
    allowed_domains: tuple[str, ...]
    allowed_ip_addresses: tuple[str, ...]


@dataclass(frozen=True)
class OllamaSidecarSpecification:
    models: tuple[str, ...]


@dataclass(frozen=True)
class McpSidecarSpecification:
    tools: tuple[str, ...]
    resources: tuple[str, ...]