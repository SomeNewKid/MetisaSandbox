"""Command-line interface for the application."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import (
    load_specification,
)
from metisa_common.specification_models import (
    MetisaSpecification,
)

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

root_directory = Path(__file__).parent
metisa_json_path = root_directory / "metisa.toml"
if not metisa_json_path.is_file():
    raise FileNotFoundError("Sample Agent missing a metisa.toml file.")
specification: MetisaSpecification = load_specification(metisa_json_path)


def main(
    argv: list[str] | None = None,
) -> int:
    """Run the sample agent workload."""
    # Interactivity
    test_interactivity(specification)

    # Internet access
    test_internet_access(specification)
    test_jina_reader(specification)

    # Localnet access
    test_database_access(specification)

    # MCP Server
    test_prompt_guard(specification)
    test_entity_guard(specification)
    test_code_execution(specification)

    # LLM Broker
    test_llm_broker(specification)

    # Document access
    test_documents(specification)
    test_docling(specification)
    test_embeddings(specification)

    _print_separator()

    return 0


def _print_separator() -> None:
    print()
    print("-" * 30, flush=True)
