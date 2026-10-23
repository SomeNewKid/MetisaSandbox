"""Entity Guard tests for the sample agent."""

from __future__ import annotations

import json

from metisa_common.specification_models import (
    Capability,
    MetisaSpecification,
)

from .._helper import (
    get_mcp_server_tool_result,
    print_caution,
    print_disabled,
    print_elapsed_time,
    print_failure,
    print_message,
    print_success,
    print_suite_title,
)

_SKIP_ENTITY_GUARD_TESTS = False


def test_entity_guard(specification: MetisaSpecification):
    """Run Entity Guard tests."""
    print_suite_title("Entity Guard")

    if _SKIP_ENTITY_GUARD_TESTS:
        print_caution("Entity Guard capability is being skipped.")
        return

    if Capability.ENTITY_GUARD not in specification.capabilities:
        print_disabled("Entity Guard capability not declared.")
        return

    _anonymize_text_sentences(
        [
            "My phone number is 9332 1234.",
            "My phone number is (08) 9332 1234.",
            "My phone number is +61 9332 1234.",
            "My phone number is 0488123456.",
            "My phone number is 0488 123 456.",
            "My name is Samantha.",
            "My name is Samantha Smith.",
            "My email is samantha.smith@example.com.",
            "My credit card number is 4111-1111-1111-1111.",
            "Our ABN is 50 110 219 460.",
            "Our ABN is 50110219460.",
            "My tax file number is 333-333-333.",
            "My tax file number is 333 333 333.",
            "My tax file number is 333333333.",
            "My Medicare number is 2428 77813 2.",
            "My Medicare number is 2428778132.",
        ]
    )


def _anonymize_text_sentences(
    sentences: list[str],
) -> None:
    if not sentences:
        return
    for sentence in sentences:
        with print_elapsed_time():
            try:
                print()
                print_message("Clear content:", sentence)
                anonymized = _anonymize_text(sentence)
                successful = anonymized != sentence
                if successful:
                    print_success("Anonymization successful for:", sentence)
                else:
                    print_failure("Anonymization failed for:", sentence)
            except Exception as error:
                print_failure("MCP server error for anonymization:", error)


def _anonymize_text(
    text: str,
) -> str:
    raw_result = get_mcp_server_tool_result(
        tool_name="anonymize_text",
        params={"text": text},
    )
    result = json.loads(raw_result)
    return result.get("anonymized")
