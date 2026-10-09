"""Provides the models to represent the Metisa TOML specification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique


@unique
class Capability(StrEnum):
    """Represents the declared capabilities of a Metisa workload."""

    INTERACTIVE = "interactive"
    NETWORK = "network"
    INTERNET = "internet"
    LOCALNET = "localnet"
    MCP_CLIENT = "mcp_client"
    JINA_READER = "jina_reader"
    CODE_EXECUTION = "code_execution"
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
    dependencies: frozenset[str]
    environs: frozenset[str]
    haproxy: HaproxySpecification | None
    squid_proxy: SquidProxySpecification | None
    ollama_sidecar: OllamaSidecarSpecification | None
    mcp_server: McpServerSpecification | None


@dataclass(frozen=True)
class HaproxySpecification:
    """Represents the HAProxy section of the Metisa specification."""

    backends: tuple[HaproxyBackend, ...]


@dataclass(frozen=True)
class HaproxyBackend:
    """Represents a backend configuration for HAProxy."""

    listen_port: int
    host: str
    port: int


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
class McpServerSpecification:
    """Represents the MCP Server section of the Metisa specification."""

    tools: tuple[str, ...]
    resources: tuple[str, ...]
    environs: frozenset[str]
