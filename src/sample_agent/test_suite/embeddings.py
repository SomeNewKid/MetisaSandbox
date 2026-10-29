"""Embeddings tests for the sample agent."""

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

_SKIP_EMBEDDINGS_TESTS = False


def test_embeddings(specification: MetisaSpecification):
    """Run Embeddings tests."""
    print_suite_title("Embeddings")

    if _SKIP_EMBEDDINGS_TESTS:
        print_caution("Embeddings capability is being skipped.")
        return

    if Capability.EMBEDDINGS not in specification.capabilities:
        print_disabled("Embeddings capability not declared.")
        return

    filename = "Employee Handbook.pdf"
    _get_get_matching_chunks(filename, "What are our company values?")
    print(flush=True)
    _get_get_matching_chunks(filename, "What is the email of the Compliance Officer?")


def _get_get_matching_chunks(filename: str, prompt: str) -> None:
    with print_elapsed_time():
        try:
            print_message(prompt)
            tool_result = get_mcp_server_tool_result(
                tool_name="get_matching_chunks",
                params={"filename": filename, "prompt": prompt},
            )

            chunks = tool_result.get("chunks", None)
            if chunks is None:
                print_failure("JSON response did not return chunks.")
                return
            if not isinstance(chunks, list):
                print_failure("JSON response did not return a list of chunks.")
                return

            any_valid = False

            separator = ""

            for chunk in chunks:
                if not isinstance(chunk, str):
                    print_failure("Received payload data item was not a string.")
                    return

                if not chunk:
                    continue

                if separator:
                    print(separator, flush=True)
                text = chunk[0:200].strip() + "..." if len(chunk) > 200 else chunk
                print_success(text)
                any_valid = True
                separator = "---"

            if not any_valid:
                print_failure("Received payload data had no non-empty items.")

        except Exception as error:
            print_failure(
                "Retrieve Embeddings sample error:",
                type(error).__name__,
                str(error),
            )
