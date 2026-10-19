"""Jina Reader tests for the sample agent."""

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


def test_jina_reader(specification: MetisaSpecification):
    """Run Jina Reader tests."""
    print_suite_title("Jina Reader")

    if Capability.JINA_READER not in specification.capabilities:
        print_skipped("Jina Reader capability not declared.")
        return

    with print_elapsed_time():
        url = "https://example.com"
        try:
            url_content = get_mcp_server_tool_result(
                tool_name="read_content_from_url",
                params={"url": url},
            )
            print_success(f"URL content from MCP Server: {url_content}")
        except Exception as error:
            print_failure("URL content from MCP Server error:", error)
