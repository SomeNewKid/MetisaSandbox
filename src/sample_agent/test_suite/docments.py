"""Documents tests for the sample agent."""

from __future__ import annotations

from metisa_common.specification_models import (
    Capability,
    MetisaSpecification,
)

from ..helper import (
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
    with print_elapsed_time():
        try:
            markdown = get_mcp_server_tool_result(
                tool_name="retrieve_from_documents",
                params={"filename": filename},
            )
            print("Data from ", filename)
            if markdown:
                if len(markdown) > 200:
                    markdown = markdown[0:200].strip() + "..."
                print_success(markdown)
            else:
                print_failure("[No data returned]")
        except Exception as error:
            print_failure(
                "Retrieve Documents sample error:",
                type(error).__name__,
                str(error),
            )

    filename = "sample.png"
    with print_elapsed_time():
        try:
            markdown = get_mcp_server_tool_result(
                tool_name="retrieve_from_documents",
                params={"filename": filename},
            )
            print("Data from ", filename)
            if markdown:
                if len(markdown) > 200:
                    markdown = markdown[0:200].strip() + "..."
                print_success(markdown)
            else:
                print_failure("[No data returned]")
        except Exception as error:
            print_failure(
                "Retrieve Documents sample error:",
                type(error).__name__,
                str(error),
            )
