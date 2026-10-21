"""Docling tests for the sample agent."""

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

_SKIP_DOCLING_TESTS = True


def test_docling(specification: MetisaSpecification):
    """Run Docling tests."""
    print_suite_title("Docling")

    if _SKIP_DOCLING_TESTS:
        print_caution("Docling capability is being skipped.")
        return

    if Capability.DOCLING not in specification.capabilities:
        print_disabled("Docling capability not declared.")
        return

    filename = "Docling Technical Report.pdf"
    with print_elapsed_time():
        try:
            markdown = get_mcp_server_tool_result(
                tool_name="extract_markdown_from_document",
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
                "Retrieve Docling sample error:",
                type(error).__name__,
                str(error),
            )
