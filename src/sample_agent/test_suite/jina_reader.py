"""Jina Reader tests for the sample agent."""

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

_SKIP_JINA_READER_TESTS = True


def test_jina_reader(specification: MetisaSpecification):
    """Run Jina Reader tests."""
    print_suite_title("Jina Reader")

    if _SKIP_JINA_READER_TESTS:
        print_caution("Jina Reader capability is being skipped.")
        return

    if Capability.JINA_READER not in specification.capabilities:
        print_disabled("Jina Reader capability not declared.")
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
