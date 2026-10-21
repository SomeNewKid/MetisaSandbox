"""Provides the models to represent the Metisa TOML specification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique


@unique
class Capability(StrEnum):
    """Represents the declared capabilities of a Metisa workload."""

    CODE_EXECUTION = "code_execution"
    DOCLING = "docling"
    DOCUMENTS = "documents"
    INTERACTIVE = "interactive"  # Legacy, but helpful with unit testing
    INTERNET = "internet"
    JINA_READER = "jina_reader"
    LLM_BROKER = "llm_broker"
    LLM_SERVER = "llm_server"
    LOCALNET = "localnet"
    MCP_SERVER = "mcp_server"
    NETWORK = "network"
    OPENAI = "openai"
    PLAYWRIGHT_CHROMIUM = "playwright_chromium"
    PROMPT_GUARD = "prompt_guard"
    ENTITY_GUARD = "entity_guard"
    QDRANT = "qdrant"
    EMBEDDINGS = "embeddings"
    OTEL_COLLECTOR = "otel_collector"


class SpecificationValidationError(ValueError):
    """Indicates that a parsed specification violates the Metisa schema."""


@dataclass(frozen=True)
class MetisaSpecification:
    """Represents the full Metisa specification."""

    agent_name: str
    capabilities: frozenset[Capability]
    dependencies: frozenset[str]
    environs: frozenset[str]
    settings: dict[str, str]
    haproxy: HaproxySpecification | None
    squid_proxy: SquidProxySpecification | None
    llm_server: LlmServerSpecification | None
    llm_broker: LlmBrokerSpecification | None
    mcp_server: McpServerSpecification | None
    jina_reader: JinaReaderSpecification | None
    code_execution: CodeExecutionSpecification | None
    docling: DoclingSpecification | None
    documents: DocumentsSpecification | None
    qdrant: QdrantSpecification | None
    embeddings: EmbeddingsSpecification | None
    otel_collector: OpenTelemetrySpecification | None


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
class DocumentsSpecification:
    """Represents the Documents section of the Metisa specification."""

    environs: frozenset[str]
    local_directory: str


@dataclass(frozen=True)
class McpServerSpecification:
    """Represents the MCP Server section of the Metisa specification."""

    tools: tuple[str, ...]
    resources: tuple[str, ...]
    environs: frozenset[str]


@dataclass(frozen=True)
class LlmBrokerSpecification:
    """Represents the LLM Broker section of the Metisa specification."""

    environs: frozenset[str]
    local_models: tuple[str, ...]
    online_models: tuple[str, ...]


@dataclass(frozen=True)
class JinaReaderSpecification:
    """Represents the Jina Reader section of the Metisa specification."""

    environs: frozenset[str]


@dataclass(frozen=True)
class DoclingSpecification:
    """Represents the Docling section of the Metisa specification."""

    environs: frozenset[str]
    embedding_model: str


@dataclass(frozen=True)
class CodeExecutionSpecification:
    """Represents the Code Execution section of the Metisa specification."""

    environs: frozenset[str]


@dataclass(frozen=True)
class QdrantSpecification:
    """Represents the Qdrant section of the Metisa specification."""

    environs: frozenset[str]


@dataclass(frozen=True)
class EmbeddingsSpecification:
    """Represents the Embeddings section of the Metisa specification."""

    environs: frozenset[str]


@dataclass(frozen=True)
class OpenTelemetrySpecification:
    """Represents the OpenTelemetry section of the Metisa specification."""

    environs: frozenset[str]
