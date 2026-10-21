"""Orchestrate and manage the Docker sandbox."""

from __future__ import annotations

import sys

from metisa_common.specification_models import MetisaSpecification
from metisa_common.terminal_helper import (
    FAILURE_INDICATOR,
    terminal_status,
)

from .code_execution_sidecar.code_execution_manager import (
    create_code_execution_container,
    create_code_execution_definition,
)
from .docker.docker_container import (
    run_docker_container,
)
from .docker.docker_network import (
    get_docker_container_ip_address,
)
from .docling_sidecar.docling_manager import (
    create_docling_container,
    create_docling_definition,
)
from .documents_sidecar.documents_manager import (
    create_documents_container,
    create_documents_definition,
)
from .embeddings_sidecar.embeddings_manager import (
    create_embeddings_container,
    create_embeddings_definition,
)
from .entity_guard_sidecar.entity_guard_manager import (
    create_entity_guard_container,
    create_entity_guard_definition,
)
from .haproxy_sidecar.haproxy_manager import (
    create_haproxy_container,
    create_haproxy_definition,
)
from .jina_reader_sidecar.jina_reader_manager import (
    create_jina_reader_container,
    create_jina_reader_definition,
)
from .llm_broker_sidecar.llm_broker_manager import (
    create_llm_broker_container,
    create_llm_broker_definition,
)
from .llm_server_sidecar.llm_server_manager import (
    create_llm_server_container,
    create_llm_server_definition,
)
from .mcp_server_sidecar.mcp_server_manager import (
    create_mcp_server_container,
    create_mcp_server_definition,
)
from .metisa_container.metisa_container_manager import (
    create_metisa_workload_container,
    create_metisa_workload_definition,
)
from .prompt_guard_sidecar.prompt_guard_manager import (
    create_prompt_guard_container,
    create_prompt_guard_definition,
)
from .qdrant_sidecar.qdrant_manager import (
    create_qdrant_container,
    create_qdrant_definition,
)
from .sandbox_container import (
    stop_and_remove_containers,
)
from .sandbox_models import (
    ContainerCreationContext,
    SandboxContainer,
    SandboxContext,
    SandboxRequirements,
)
from .sandbox_network import (
    create_sandbox_network,
    define_sandbox_network,
    remove_sandbox_networks,
)
from .sandbox_workspace import (
    clean_up_run_directory,
    create_sandbox_context,
)
from .squid_proxy_sidecar.squid_proxy_manager import (
    create_squid_proxy_container,
    create_squid_proxy_definition,
)
from .utilities.workspace_helper import (
    clean_up_staged_sources,
)


def run_metisa_container_workload_in_sandbox(
    specification: MetisaSpecification,
    image_reference: str,
    workload_module: str,
) -> int:
    """Run the specified workload in a Docker sandbox."""
    sandbox_requirements = SandboxRequirements(specification)

    sandbox_context: SandboxContext = create_sandbox_context()
    sc = sandbox_context

    workload_network = define_sandbox_network(
        "workload", sc.workload_network_name, True
    )
    backend_network = define_sandbox_network("backend", sc.backend_network_name, True)
    egress_network = define_sandbox_network("egress", sc.egress_network_name, False)

    all_networks = [
        workload_network,
        backend_network,
        egress_network,
    ]

    metisa_workload_container = create_metisa_workload_definition()
    squid_proxy_container = create_squid_proxy_definition()
    haproxy_container = create_haproxy_definition()
    mcp_server_container = create_mcp_server_definition()
    jina_reader_container = create_jina_reader_definition()
    code_execution_container = create_code_execution_definition()
    llm_broker_container = create_llm_broker_definition()
    prompt_guard_container = create_prompt_guard_definition()
    entity_guard_container = create_entity_guard_definition()
    docling_container = create_docling_definition()
    documents_container = create_documents_definition()
    qdrant_container = create_qdrant_definition()
    embeddings_container = create_embeddings_definition()

    all_containers = [
        metisa_workload_container,
        squid_proxy_container,
        haproxy_container,
        mcp_server_container,
        jina_reader_container,
        code_execution_container,
        llm_broker_container,
        prompt_guard_container,
        entity_guard_container,
        docling_container,
        documents_container,
        qdrant_container,
        embeddings_container,
    ]

    try:
        if sandbox_requirements.is_workload_network_required:
            create_sandbox_network(workload_network)

        if sandbox_requirements.is_backend_network_required:
            create_sandbox_network(backend_network)

        if sandbox_requirements.is_egress_network_required:
            create_sandbox_network(egress_network)

            if sandbox_requirements.is_internet_access_required:
                _create_squid_proxy_container(
                    specification,
                    sandbox_requirements,
                    sandbox_context,
                    squid_proxy_container,
                )

        if sandbox_requirements.is_llm_broker_required:
            _create_llm_broker_container(
                specification,
                sandbox_context,
                squid_proxy_container,
                llm_broker_container,
            )

        if sandbox_requirements.is_llm_server_required and specification.llm_server:
            all_containers.extend(
                _create_llm_server_containers(
                    specification,
                    sandbox_context,
                    squid_proxy_container,
                )
            )

        if sandbox_requirements.is_jina_reader_required:
            _create_jina_reader_container(
                specification,
                sandbox_context,
                squid_proxy_container,
                jina_reader_container,
            )

        if sandbox_requirements.is_code_execution_required:
            _create_code_execution_container(
                specification,
                sandbox_context,
                squid_proxy_container,
                code_execution_container,
            )

        if sandbox_requirements.is_mcp_server_required:
            _create_mcp_server_container(
                specification,
                sandbox_context,
                squid_proxy_container,
                mcp_server_container,
            )

        if sandbox_requirements.is_docling_required:
            _create_docling_container(
                specification,
                sandbox_context,
                squid_proxy_container,
                docling_container,
            )

        if sandbox_requirements.is_documents_required:
            _create_documents_container(
                specification,
                sandbox_context,
                squid_proxy_container,
                documents_container,
            )

        if (
            sandbox_requirements.is_mcp_server_required
            or sandbox_requirements.is_llm_broker_required
        ):
            _create_prompt_guard_container(
                specification,
                sandbox_context,
                squid_proxy_container,
                prompt_guard_container,
            )

            _create_entity_guard_container(
                specification,
                sandbox_context,
                squid_proxy_container,
                entity_guard_container,
            )

        if sandbox_requirements.is_localnet_access_required:
            _create_haproxy_container(
                specification,
                sandbox_requirements,
                sandbox_context,
                squid_proxy_container,
                mcp_server_container,
                haproxy_container,
            )

        if sandbox_requirements.is_qdrant_required:
            _create_qdrant_container(
                specification,
                sandbox_context,
                squid_proxy_container,
                qdrant_container,
            )

        if sandbox_requirements.is_embeddings_required:
            _create_embeddings_container(
                specification,
                sandbox_context,
                squid_proxy_container,
                embeddings_container,
            )

        _create_metisa_workload_container(
            specification,
            image_reference,
            workload_module,
            sandbox_requirements,
            sandbox_context,
            squid_proxy_container,
            metisa_workload_container,
        )

        return run_docker_container(metisa_workload_container.instance_name)

    finally:
        if sandbox_context is not None:
            try:
                cleanup_errors: list[str] = []

                stop_and_remove_containers(
                    sandbox_context,
                    cleanup_errors,
                    all_containers,
                )

                remove_sandbox_networks(
                    all_networks,
                    cleanup_errors,
                )

                for cleanup_error in cleanup_errors:
                    print(f"{FAILURE_INDICATOR} {cleanup_error}", file=sys.stderr)

            finally:
                clean_up_run_directory(
                    sandbox_context.host_output_path,
                    sandbox_context.host_logs_path,
                    sandbox_context.host_scratch_path,
                )

                clean_up_staged_sources(all_containers)


def _create_metisa_workload_container(
    specification: MetisaSpecification,
    image_reference: str,
    workload_module: str,
    sandbox_requirements: SandboxRequirements,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    metisa_workload_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating Metisa Workload container.",
        success="Created Metisa Workload container.",
        failure="Could not create Metisa Workload container.",
    ):
        metisa_workload_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.workload_network_name,
            ],
        )
        use_squid_proxy = _workload_container_needs_squid_proxy(sandbox_requirements)
        metisa_settings = metisa_workload_creation_context.settings
        metisa_settings["image_reference"] = image_reference
        metisa_settings["workload_module"] = workload_module
        metisa_settings["use_squid_proxy"] = use_squid_proxy
        metisa_settings["is_network_required"] = (
            sandbox_requirements.is_workload_network_required
        )

        metisa_workload_creation = create_metisa_workload_container(
            specification,
            sandbox_context,
            metisa_workload_creation_context,
        )
        metisa_workload_container.set_created(metisa_workload_creation)


def _create_haproxy_container(
    specification: MetisaSpecification,
    sandbox_requirements: SandboxRequirements,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    mcp_server_container: SandboxContainer,
    haproxy_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating HAProxy container...",
        success="Created HAProxy container.",
        failure="Could not create HAProxy container.",
    ):
        haproxy_target_network_name = (
            sandbox_context.backend_network_name
            if sandbox_requirements.is_backend_network_required
            else sandbox_context.workload_network_name
        )
        haproxy_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.egress_network_name,
                haproxy_target_network_name,
            ],
        )
        mcp_server_ip = mcp_server_container.network_ip_address
        haproxy_creation_context.mcp_server_ip_address = mcp_server_ip

        haproxy_creation = create_haproxy_container(
            specification,
            sandbox_context,
            haproxy_creation_context,
        )
        haproxy_container.set_created(haproxy_creation)


def _create_prompt_guard_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    prompt_guard_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating Prompt Guard container...",
        success="Created Prompt Guard container.",
        failure="Could not create Prompt Guard container.",
    ):
        prompt_guard_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.backend_network_name,
            ],
        )
        prompt_guard_creation = create_prompt_guard_container(
            specification, sandbox_context, prompt_guard_creation_context
        )
        prompt_guard_container.set_created(prompt_guard_creation)


def _create_entity_guard_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    entity_guard_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating Entity Guard container...",
        success="Created Entity Guard container.",
        failure="Could not create Entity Guard container.",
    ):
        entity_guard_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.backend_network_name,
            ],
        )
        entity_guard_creation = create_entity_guard_container(
            specification, sandbox_context, entity_guard_creation_context
        )
        entity_guard_container.set_created(entity_guard_creation)


def _create_mcp_server_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    mcp_server_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating MCP Server container...",
        success="Created MCP Server container.",
        failure="Could not create MCP Server container.",
    ):
        mcp_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.workload_network_name,
                sandbox_context.backend_network_name,
            ],
        )
        mcp_server_creation = create_mcp_server_container(
            specification,
            sandbox_context,
            mcp_creation_context,
        )
        mcp_server_container.set_created(mcp_server_creation)
        mcp_server_container.network_ip_address = get_docker_container_ip_address(
            mcp_server_container.instance_name,
            sandbox_context.backend_network_name,
        )


def _create_code_execution_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    code_execution_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating Code Execution container...",
        success="Created Code Execution container.",
        failure="Could not create Code Execution container.",
    ):
        code_execution_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.backend_network_name,
            ],
        )
        code_execution_creation = create_code_execution_container(
            specification, sandbox_context, code_execution_creation_context
        )
        code_execution_container.set_created(code_execution_creation)


def _create_jina_reader_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    jina_reader_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating Jina Reader container...",
        success="Created Jina Reader container.",
        failure="Could not create Jina Reader container.",
    ):
        jina_reader_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.backend_network_name,
            ],
        )
        jina_reader_creation = create_jina_reader_container(
            specification, sandbox_context, jina_reader_creation_context
        )
        jina_reader_container.set_created(jina_reader_creation)


def _create_docling_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    docling_container: SandboxContainer,
) -> None:
    if not specification.docling:
        raise RuntimeError("Docling specification must be provided.")
    embedding_model = specification.docling.embedding_model
    if not embedding_model:
        error = "Embedding model must be specified for the Docling container."
        raise RuntimeError(error)

    with terminal_status(
        running="Creating Docling container...",
        success="Created Docling container.",
        failure="Could not create Docling container.",
    ):
        docling_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.backend_network_name,
            ],
        )
        docling_creation_context.settings["embedding_model"] = embedding_model
        docling_creation = create_docling_container(
            specification, sandbox_context, docling_creation_context
        )
        docling_container.set_created(docling_creation)


def _create_documents_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    documents_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating Documents container...",
        success="Created Documents container.",
        failure="Could not create Documents container.",
    ):
        documents_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.backend_network_name,
            ],
        )
        documents_creation = create_documents_container(
            specification, sandbox_context, documents_creation_context
        )
        documents_container.set_created(documents_creation)


def _create_qdrant_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    qdrant_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating Qdrant container...",
        success="Created Qdrant container.",
        failure="Could not create Qdrant container.",
    ):
        qdrant_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.backend_network_name,
            ],
        )
        qdrant_creation = create_qdrant_container(
            specification, sandbox_context, qdrant_creation_context
        )
        qdrant_container.set_created(qdrant_creation)


def _create_llm_server_containers(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
) -> list[SandboxContainer]:
    assert specification.llm_server is not None
    created_containers = []
    for llm_model in specification.llm_server.models:
        with terminal_status(
            running=f"Creating LLM ({llm_model.alias}) container...",
            success=f"Created LLM ({llm_model.alias}) container.",
            failure=f"Could not create LLM ({llm_model.alias}) container.",
        ):
            llm_alias = llm_model.alias
            llm_model_container = create_llm_server_definition(llm_alias)
            created_containers.append(llm_model_container)

            llm_server_creation_context = _create_creation_context(
                squid_proxy_container=squid_proxy_container,
                network_names=[
                    sandbox_context.backend_network_name,
                ],
            )
            llm_server_creation_context.settings["llm_model"] = llm_model

            llm_server_creation = create_llm_server_container(
                specification, sandbox_context, llm_server_creation_context
            )
            llm_model_container.set_created(llm_server_creation)
    return created_containers


def _create_llm_broker_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    llm_broker_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating LLM Broker container...",
        success="Created LLM Broker container.",
        failure="Could not create LLM Broker container.",
    ):
        llm_broker_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.backend_network_name,
                sandbox_context.workload_network_name,
            ],
        )
        llm_broker_creation = create_llm_broker_container(
            specification, sandbox_context, llm_broker_creation_context
        )
        llm_broker_container.set_created(llm_broker_creation)


def _create_squid_proxy_container(
    specification: MetisaSpecification,
    sandbox_requirements: SandboxRequirements,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
) -> None:
    with terminal_status(
        running="Creating Squid Proxy container...",
        success="Created Squid Proxy container.",
        failure="Could not create Squid Proxy container.",
    ):
        squid_proxy_networks = [sandbox_context.egress_network_name]
        if sandbox_requirements.is_backend_network_required:
            squid_proxy_networks.append(sandbox_context.backend_network_name)
        if (
            _workload_container_needs_squid_proxy(sandbox_requirements)
            or not sandbox_requirements.is_backend_network_required
        ):
            squid_proxy_networks.append(sandbox_context.workload_network_name)

        squid_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=squid_proxy_networks,
        )
        squid_proxy_creation = create_squid_proxy_container(
            specification, sandbox_context, squid_creation_context
        )
        squid_proxy_container.set_created(squid_proxy_creation)


def _create_embeddings_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    squid_proxy_container: SandboxContainer,
    embeddings_container: SandboxContainer,
) -> None:
    if not specification.docling:
        raise RuntimeError("Docling specification must be provided.")
    embedding_model = specification.docling.embedding_model
    if not embedding_model:
        error = "Embedding model must be specified for the Docling container."
        raise RuntimeError(error)

    with terminal_status(
        running="Creating Embeddings container...",
        success="Created Embeddings container.",
        failure="Could not create Embeddings container.",
    ):
        embeddings_creation_context = _create_creation_context(
            squid_proxy_container=squid_proxy_container,
            network_names=[
                sandbox_context.backend_network_name,
            ],
        )
        embeddings_creation_context.settings["embedding_model"] = embedding_model
        embeddings_creation = create_embeddings_container(
            specification, sandbox_context, embeddings_creation_context
        )
        embeddings_container.set_created(embeddings_creation)


def _create_creation_context(
    *,
    squid_proxy_container: SandboxContainer,
    network_names: list[str],
) -> ContainerCreationContext:
    container_creation_context = ContainerCreationContext()
    container_creation_context.squid_proxy_url = squid_proxy_container.network_url
    container_creation_context.network_names = network_names
    return container_creation_context


def _workload_container_needs_squid_proxy(
    sandbox_requirements: SandboxRequirements,
) -> bool:
    return (
        sandbox_requirements.is_internet_access_required
        and not sandbox_requirements.is_llm_broker_required
    )
