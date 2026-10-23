"""Command-line interface for the application."""

from __future__ import annotations

from pathlib import Path

from opentelemetry import trace
from opentelemetry.context import Context

from metisa_common.specification_helper import (
    load_specification,
)
from metisa_common.specification_models import (
    Capability,
    MetisaSpecification,
)

from ._telemetry import initialize_tracing
from .test_suite.code_execution import test_code_execution
from .test_suite.database import test_database_access
from .test_suite.docling import test_docling
from .test_suite.documents import test_documents
from .test_suite.embeddings import test_embeddings
from .test_suite.entity_guard import test_entity_guard
from .test_suite.interactivity import test_interactivity
from .test_suite.internet import test_internet_access
from .test_suite.jina_reader import test_jina_reader
from .test_suite.llm_broker import test_llm_broker
from .test_suite.prompt_guard import test_prompt_guard
from .test_suite.secrets import test_secrets
from .test_suite.tracing import test_tracing

root_directory = Path(__file__).parent
metisa_json_path = root_directory / "metisa.toml"
if not metisa_json_path.is_file():
    raise FileNotFoundError("Sample Agent missing a metisa.toml file.")
specification: MetisaSpecification = load_specification(metisa_json_path)


def main(
    argv: list[str] | None = None,
) -> int:
    """Run the sample agent workload."""
    provider = None

    if Capability.OTEL_COLLECTOR in specification.capabilities:
        provider = initialize_tracing()

    # OpenTelemetry supports instrumentation without an initialized SDK provider.
    # Calls such as trace.get_tracer() and start_as_current_span()
    # do not record or export spans until the provider is configured.
    try:
        tracer = trace.get_tracer("sample_agent")

        with tracer.start_as_current_span("sample_agent.run", context=Context()):
            _run_tests(specification)

        return 0

    finally:
        if provider is not None:
            provider.shutdown()


def _run_tests(specification: MetisaSpecification) -> None:
    test_tracing(specification)
    test_interactivity(specification)
    test_internet_access(specification)
    test_jina_reader(specification)
    test_database_access(specification)
    test_prompt_guard(specification)
    test_entity_guard(specification)
    test_code_execution(specification)
    test_llm_broker(specification)
    test_documents(specification)
    test_docling(specification)
    test_embeddings(specification)
    test_secrets(specification)

    print()
    print("-" * 30, flush=True)
