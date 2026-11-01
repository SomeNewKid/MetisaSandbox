"""Documents tests for the sample agent."""

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
    print_success,
    print_suite_title,
)

_SKIP_DOCUMENTS_TESTS = False


def test_documents(specification: MetisaSpecification):
    """Run Documents tests."""
    print_suite_title("Documents")

    if _SKIP_DOCUMENTS_TESTS:
        print_caution("Documents capability is being skipped.")
        return

    if Capability.DOCUMENTS not in specification.capabilities:
        print_disabled("Documents capability not declared.")
        return

    filename = "sample.txt"
    print("Data from ", filename, flush=True)
    with print_elapsed_time():
        try:
            tool_result = get_mcp_server_tool_result(
                tool_name="retrieve_content_from_document",
                params={"filename": filename},
            )
            markdown = tool_result.get("content", None)
            if markdown is None:
                print_failure("No content returned.")
                return
            if not isinstance(markdown, str):
                print_failure("Returned content not a string.")
                return
            if markdown:
                if len(markdown) > 200:
                    markdown = markdown[0:200].strip() + "..."
                print_success(markdown)
            else:
                print_failure("[No data returned]")
        except Exception as error:
            print_failure(
                "Retrieve sample document error:",
                type(error).__name__,
                str(error),
            )

    filename = "prompt-injection.txt"
    print()
    print("Data from ", filename, flush=True)
    with print_elapsed_time():
        try:
            tool_result = get_mcp_server_tool_result(
                tool_name="retrieve_content_from_document",
                params={"filename": filename},
            )
            markdown = tool_result.get("content", None)
            if markdown is None:
                markdown = "[No content returned]"
            if not isinstance(markdown, str):
                markdown = "[Non-string content returned]"
            if markdown:
                if len(markdown) > 200:
                    markdown = markdown[0:200].strip() + "..."
            else:
                markdown = "[Empty content returned]"
            print_failure("Prompt injection document did not raise error.", markdown)
        except Exception:
            print_success("Prompt injection document raised an error.")
