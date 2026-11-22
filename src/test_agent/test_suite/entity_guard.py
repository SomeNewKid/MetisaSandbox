"""Entity Guard tests for the sample agent."""

from __future__ import annotations

from metisa_common.clients.mcp_client import (
    get_mcp_server_tool_result,
)
from metisa_common.specification_models import (
    Capability,
    MetisaSpecification,
)

from .._helper import (
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

_NEUTRAL_SENTENCES = [
    "My name is Samantha.",
]

_EXTENSIVE_TEST_SENTENCES = [
    "My phone number is 9332 1234.",
    "My phone number is (08) 9332 1234.",
    "My phone number is +61 9332 1234.",
    "My phone number is 0488123456.",
    "My phone number is 0488 123 456.",
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

_EXTENSIVE_NEUTRAL_SENTENCES = [
    "The sky is blue.",
    "My name is my own.",
    "My name is Samantha.",
    "My email is private.",
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
        _anonymize_entities_in_text_sentences(_EXTENSIVE_TEST_SENTENCES, True)
        _anonymize_entities_in_text_sentences(_EXTENSIVE_NEUTRAL_SENTENCES, False)
    else:
        _anonymize_entities_in_text_sentences(_TEST_SENTENCES, True)
        _anonymize_entities_in_text_sentences(_NEUTRAL_SENTENCES, False)


def _anonymize_entities_in_text_sentences(
    sentences: list[str],
    expect_anonymization: bool = True,
) -> None:
    if not sentences:
        return
    for sentence in sentences:
        with print_elapsed_time():
            try:
                if sentence != _TEST_SENTENCES[0]:
                    print()
                print_message("Clear content:", sentence)
                anonymized = _anonymize_entities_in_text(sentence)
                successful = (
                    anonymized != sentence
                    if expect_anonymization
                    else anonymized == sentence
                )
                if successful:
                    print_success("Anonymization successful for:", anonymized)
                else:
                    print_failure("Anonymization failed for:", anonymized)
            except Exception as error:
                print_failure("MCP server error for anonymization:", error)


def _anonymize_entities_in_text(
    text: str,
) -> str:
    tool_result = get_mcp_server_tool_result(
        tool_name="anonymize_entities_in_text",
        params={"text": text},
    )
    anonymized = tool_result.get("anonymized", None)
    if anonymized is None:
        raise RuntimeError("Tool result did not include anonymized text.")
    if not isinstance(anonymized, str):
        raise RuntimeError("Tool result for anonymized was not a string.")

    return anonymized
