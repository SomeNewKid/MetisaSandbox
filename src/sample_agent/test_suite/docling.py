"""Docling tests for the sample agent."""

from __future__ import annotations

from metisa_common.specification_models import (
    Capability,
    MetisaSpecification,
)

from ..helper import (
    get_mcp_server_tool_result,
    print_elapsed_time,
    print_failure,
    print_skipped,
    print_success,
    print_suite_title,
)


def test_docling(specification: MetisaSpecification):
    """Run Docling tests."""
    print_suite_title("Docling")

    if Capability.DOCLING not in specification.capabilities:
        print_skipped("Docling capability not declared.")
        return

    url = "https://www.example.com"
    with print_elapsed_time():
        try:
            markdown = get_mcp_server_tool_result(
                tool_name="convert_to_markdown",
                params={"url": url},
            )
            print("Markdown from ", url)
            if markdown:
                print_success(markdown)
            else:
                print_failure("[No Markdown returned]")
        except Exception as error:
            print_failure("URL to Markdown conversion error:", error)
