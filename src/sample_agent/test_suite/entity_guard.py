"""Entity Guard tests for the sample agent."""

from __future__ import annotations

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
_USE_EXTENSIVE_TEST_SENTENCES = False

_TEST_SENTENCES = [
    "My phone number is (08) 9332 1234.",
    "My name is Samantha Smith.",
    "My email is samantha.smith@example.com.",
    "My credit card number is 4111-1111-1111-1111.",
    "My Medicare number is 2428 77813 2.",
]

_EXTENSIVE_TEST_SENTENCES = [
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


def test_entity_guard(specification: MetisaSpecification):
    """Run Entity Guard tests."""
    print_suite_title("Entity Guard")

    if _SKIP_ENTITY_GUARD_TESTS:
        print_caution("Entity Guard capability is being skipped.")
        return

    if Capability.ENTITY_GUARD not in specification.capabilities:
        print_disabled("Entity Guard capability not declared.")
        return

    if _USE_EXTENSIVE_TEST_SENTENCES:
        _anonymize_text_sentences(_EXTENSIVE_TEST_SENTENCES)
    else:
        _anonymize_text_sentences(_TEST_SENTENCES)


def _anonymize_text_sentences(
    sentences: list[str],
) -> None:
    if not sentences:
        return
    for sentence in sentences:
        with print_elapsed_time():
            try:
                if sentence != _TEST_SENTENCES[0]:
                    print()
                print_message("Clear content:", sentence)
                anonymized = _anonymize_text(sentence)
                successful = anonymized != sentence
                if successful:
                    print_success("Anonymization successful for:", anonymized)
                else:
                    print_failure("Anonymization failed for:", anonymized)
            except Exception as error:
                print_failure("MCP server error for anonymization:", error)


def _anonymize_text(
    text: str,
) -> str:
    tool_result = get_mcp_server_tool_result(
        tool_name="anonymize_text",
        params={"text": text},
    )
    anonymized = tool_result.get("anonymized", None)
    if anonymized is None:
        raise RuntimeError("Tool result did not include anonymized text.")
    if not isinstance(anonymized, str):
        raise RuntimeError("Tool result for anonymized was not a string.")

    return anonymized
