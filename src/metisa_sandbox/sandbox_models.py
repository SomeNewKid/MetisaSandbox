"""Models providing abstractions for the Docker sandbox."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from metisa_common.specification_models import Capability, MetisaSpecification

from .docker.docker_container import remove_docker_container


@dataclass(frozen=True)
class SandboxContext:
    """Contextual information for a Docker sandbox."""

    run_identifier: str
    workload_container_name: str

    workload_network_name: str
    backend_network_name: str
    egress_network_name: str

    host_run_path: Path
    host_output_path: Path
    host_logs_path: Path
    host_scratch_path: Path


class SandboxRequirements:
    """Requirements for a Docker sandbox."""

    def __init__(self, specification: MetisaSpecification):
        """Initialize a new instance of the SandboxRequirements."""
        self._specification = specification

    @property
    def is_mcp_server_required(self) -> bool:
        """Returns a flag indicating if the MCP Server is required."""
        return Capability.MCP_SERVER in self._specification.capabilities

    @property
    def is_jina_reader_required(self) -> bool:
        """Returns a flag indicating if the Jina Reader sidecar is required."""
        return Capability.JINA_READER in self._specification.capabilities

    @property
    def is_code_execution_required(self) -> bool:
        """Returns a flag indicating if the Code Execution sidecar is required."""
        return Capability.CODE_EXECUTION in self._specification.capabilities

    @property
    def is_llm_broker_required(self) -> bool:
        """Returns a flag indicating if the LLM Broker is required."""
        return Capability.LLM_BROKER in self._specification.capabilities

    @property
    def is_llm_server_required(self) -> bool:
        """Returns a flag indicating if the LLM Server sidecars are required."""
        return Capability.LLM_SERVER in self._specification.capabilities

    @property
    def is_docling_required(self) -> bool:
        """Returns a flag indicating if the Docling sidecar is required."""
        return Capability.DOCLING in self._specification.capabilities

    @property
    def is_documents_required(self) -> bool:
        """Returns a flag indicating if the Documents sidecar is required."""
        return Capability.DOCUMENTS in self._specification.capabilities

    @property
    def is_qdrant_required(self) -> bool:
        """Returns a flag indicating if the Qdrant sidecar is required."""
        return Capability.QDRANT in self._specification.capabilities

    @property
    def is_embeddings_required(self) -> bool:
        """Returns a flag indicating if the Embeddings sidecar is required."""
        return Capability.EMBEDDINGS in self._specification.capabilities

    @property
    def is_internet_access_required(self) -> bool:
        """Returns a flag indicating if internet access is required."""
        return Capability.INTERNET in self._specification.capabilities

    @property
    def is_localnet_access_required(self) -> bool:
        """Returns a flag indicating if local network access is required."""
        return Capability.LOCALNET in self._specification.capabilities

    @property
    def is_workload_network_required(self) -> bool:
        """Returns a flag indicating if an internal workload network is required."""
        return Capability.NETWORK in self._specification.capabilities

    @property
    def is_backend_network_required(self) -> bool:
        """Returns a flag indicating if an internal backend network is required."""
        return self.is_mcp_server_required or self.is_llm_broker_required

    @property
    def is_egress_network_required(self) -> bool:
        """Returns a flag indicating if an engress network is required."""
        return self.is_internet_access_required or self.is_localnet_access_required


class SandboxContainer:
    """Represent a Docker container."""

    def __init__(
        self,
        title: str,
        name: str,
        *,
        network_alias: str | None = None,
        network_ip_address: str | None = None,
        network_url: str | None = None,
        staged_source: Path | None = None,
        log_folder: str | None = None,
        log_files: list[str] | None = None,
    ):
        """Initialize a new instance of a SandboxContainer."""
        self._title = self._validate_title(title)
        self._name = self._validate_name(name)
        self._instance_name: str | None = None
        self._is_created = False
        self._network_alias: str | None = network_alias or name
        self._network_ip_address: str | None = network_ip_address
        self._network_url: str | None = network_url
        self._staged_source: Path | None = staged_source
        self._log_folder: str | None = log_folder
        self._log_files: list[str] = log_files or []

    @property
    def title(self) -> str:
        """Return the display title of the Docker container."""
        return self._title

    @property
    def name(self) -> str:
        """Return the name of the Docker container."""
        return self._name

    @property
    def instance_name(self) -> str:
        """Return the instance name of the Docker container."""
        if not self.is_created or not self._instance_name:
            raise RuntimeError(f"Container has not been created ('{self._name}').")
        return self._instance_name

    @property
    def network_alias(self) -> str | None:
        """Get the network alias of the container."""
        return self._network_alias

    @network_alias.setter
    def network_alias(self, value: str | None) -> None:
        """Set the network alias of the container."""
        self._network_alias = value

    @property
    def network_ip_address(self) -> str | None:
        """Get the network IP address of the container."""
        return self._network_ip_address

    @network_ip_address.setter
    def network_ip_address(self, value: str | None) -> None:
        """Set the network IP address of the container."""
        self._network_ip_address = value

    @property
    def network_url(self) -> str | None:
        """Get the network URL of the container."""
        return self._network_url

    @network_url.setter
    def network_url(self, value: str | None) -> None:
        """Set the network URL of the container."""
        self._network_url = value

    @property
    def staged_source(self) -> Path | None:
        """Get the path to the staged source of the container."""
        return self._staged_source

    @staged_source.setter
    def staged_source(self, value: Path | None) -> None:
        """Set the path to the staged source of the container."""
        self._staged_source = value

    @property
    def log_folder(self) -> str | None:
        """Get the name of the folder for the logged files of the container."""
        return self._log_folder

    @log_folder.setter
    def log_folder(self, value: str | None) -> None:
        """Set the name of the folder for the logged files of the container."""
        self._log_folder = value

    @property
    def log_files(self) -> list[str]:
        """Get the locations of the files to be logged for the container."""
        return self._log_files

    @log_files.setter
    def log_files(self, value: list[str]) -> None:
        """Set the locations of the files to be logged for the container."""
        self._log_files = value

    @property
    def is_created(self) -> bool:
        """Return a flag indicating if the container has been created."""
        return self._is_created

    def set_created(self, creation_result: ContainerCreationResult) -> None:
        """Mark the container as having been created."""
        self._instance_name = creation_result.container_name
        self._staged_source = creation_result.staged_source
        self._is_created = True

    def remove(self) -> None:
        """Remove the Docker container."""
        if not self._is_created:
            return
        remove_docker_container(self._name)
        self._is_created = False

    def _validate_title(self, title: str) -> str:
        if not title:
            raise ValueError("Title cannot be empty.")
        return title

    def _validate_name(self, name: str) -> str:
        if not name.strip():
            raise ValueError("Name cannot be empty.")
        if not re.fullmatch(r"[a-z][a-z0-9_]+[a-z]", name):
            raise ValueError(
                "Name can only contain letters, numbers, and underscores, "
                "and must start and end with a letter."
            )
        return name


class ContainerCreationContext:
    """The context for the creation of a sandbox container."""

    def __init__(self):
        """Initialize a new instance of the ContainerCreationContext."""
        self._squid_proxy_url: str | None = None
        self._mcp_server_ip_address: str | None = None
        self._network_names: list[str] = []
        self._settings: dict[str, object] = {}

    @property
    def squid_proxy_url(self) -> str | None:
        """Get the Squid Proxy URL."""
        return self._squid_proxy_url

    @squid_proxy_url.setter
    def squid_proxy_url(self, value: str | None) -> None:
        """Set the Squid Proxy URL."""
        self._squid_proxy_url = value

    @property
    def mcp_server_ip_address(self) -> str | None:
        """Get the IP address of the MCP server."""
        return self._mcp_server_ip_address

    @mcp_server_ip_address.setter
    def mcp_server_ip_address(self, value: str | None) -> None:
        """Set the IP address of the MCP server."""
        self._mcp_server_ip_address = value

    @property
    def network_names(self) -> list[str]:
        """Get the names of the network to which the container should be attached."""
        return self._network_names

    @network_names.setter
    def network_names(self, network_names: list[str]) -> None:
        """Set the names of the network to which the container should be attached."""
        self._network_names = network_names

    @property
    def settings(self) -> dict[str, object]:
        """Get the settings for the container creation context."""
        return self._settings


@dataclass(frozen=True)
class ContainerCreationResult:
    """The result of creating a container."""

    container_name: str
    staged_source: Path | None = None


class SandboxNetwork:
    """Represent a Docker network."""

    def __init__(self, title: str, name: str, is_internal: bool):
        """Initialize a new instance of a SandboxNetwork."""
        self._title = title
        self._name = name
        self._is_internal = is_internal
        self._is_created = False

    @property
    def title(self) -> str:
        """Return the friendly title of the Docker network."""
        return self._title

    @property
    def name(self) -> str:
        """Return the instance name of the Docker network."""
        return self._name

    @property
    def is_internal(self) -> bool:
        """Return a flag indicating if the network is internal."""
        return self._is_internal

    @property
    def is_created(self) -> bool:
        """Returna flag indicating if the network has been created."""
        return self._is_created

    def set_created(self) -> None:
        """Mark the Docker network as created."""
        self._is_created = True

    def set_removed(self) -> None:
        """Mark the Docker network as removed."""
        if not self._is_created:
            return
        self._is_created = False
