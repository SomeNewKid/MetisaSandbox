"""Provides the models to represent the Metisa TOML specification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique


@unique
class Capability(StrEnum):
    """Represents the declared capabilities of a Metisa workload."""

    INTERACTIVE = "interactive"
    NETWORK = "network"
    MCP_CLIENT = "mcp_client"
    JINA_READER = "jina_reader"
    CODE_EXECUTION = "code_execution"
    HAPROXY = "haproxy"
    OLLAMA = "ollama"
    PLAYWRIGHT_CHROMIUM = "playwright_chromium"
    OPENAI = "openai"


class SpecificationValidationError(ValueError):
    """Indicates that a parsed specification violates the Metisa schema."""


@dataclass(frozen=True)
class MetisaSpecification:
    """Represents the full Metisa specification."""

    agent_name: str
    capabilities: frozenset[Capability]
    haproxy: HaproxySpecification | None
    squid_proxy: SquidProxySpecification | None
    ollama_sidecar: OllamaSidecarSpecification | None
    mcp_sidecar: McpSidecarSpecification | None


@dataclass(frozen=True)
class HaproxySpecification:
    """Represents the HAProxy section of the Metisa specification."""

    ports: tuple[int, ...]


@dataclass(frozen=True)
class SquidProxySpecification:
    """Represents the Squid Proxy section of the Metisa specification."""

    allowed_domains: tuple[str, ...]
    allowed_ip_addresses: tuple[str, ...]


@dataclass(frozen=True)
class OllamaSidecarSpecification:
    """Represents the Ollama Sidecar section of the Metisa specification."""

    models: tuple[str, ...]


@dataclass(frozen=True)
class McpSidecarSpecification:
    """Represents the MCP Sidecar section of the Metisa specification."""

    tools: tuple[str, ...]
    resources: tuple[str, ...]
