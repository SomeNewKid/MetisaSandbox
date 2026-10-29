"""Jina Reader tests for the sample agent."""

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

_SKIP_JINA_READER_TESTS = False


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
            tooL_result = get_mcp_server_tool_result(
                tool_name="read_content_from_url",
                params={"url": url},
            )
            content = tooL_result.get("content", None)
            if content is None:
                print_failure("URL content not returned from MCP Server error:")
                return
            if not isinstance(content, str):
                print_failure("URL content from MCP Server was not a string.")
                return
            if len(content) > 200:
                content = content[:200].strip() + "..."
            print_success(f"URL content from MCP Server: {content}")
        except Exception as error:
            print_failure("URL content from MCP Server error:", error)
