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
    MCP_SERVER = "mcp_server"
    JINA_READER = "jina_reader"
    CODE_EXECUTION = "code_execution"
    LLM_SERVER = "llm_server"
    PROMPT_GUARD = "prompt_guard"
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
    llm_server: LlmServerSpecification | None
    mcp_server: McpServerSpecification | None
    jina_reader: JinaReaderSpecification | None
    code_execution: CodeExecutionSpecification | None


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
class LlmServerSpecification:
    """Represents the LLM Server section of the Metisa specification."""

    models: tuple[LlmModel, ...]


@dataclass(frozen=True)
class LlmModel:
    """Represents a large language model."""

    alias: str
    repo: str
    revision: str
    filename: str


@dataclass(frozen=True)
class McpServerSpecification:
    """Represents the MCP Server section of the Metisa specification."""

    tools: tuple[str, ...]
    resources: tuple[str, ...]
    environs: frozenset[str]


@dataclass(frozen=True)
class JinaReaderSpecification:
    """Represents the Jina Reader section of the Metisa specification."""

    environs: frozenset[str]


@dataclass(frozen=True)
class CodeExecutionSpecification:
    """Represents the Code Execution section of the Metisa specification."""

    environs: frozenset[str]
