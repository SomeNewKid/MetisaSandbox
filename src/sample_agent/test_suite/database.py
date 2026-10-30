"""Database tests for the sample agent."""

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

_SKIP_DATABASE_TESTS = False


def test_database_access(specification: MetisaSpecification):
    """Run database access tests."""
    print_suite_title("Database")

    if _SKIP_DATABASE_TESTS:
        print_caution("Database capability is being skipped.")
        return

    if Capability.LOCALNET not in specification.capabilities:
        print_disabled("Localnet capability not declared.")
        return

    with print_elapsed_time():
        try:
            tool_call_result = get_mcp_server_tool_result(
                tool_name="get_active_items",
            )
            items = tool_call_result.get("items", None)
            if items is None:
                print_failure("Database records not returned by MCP server.")
                return
            if not isinstance(items, list):
                print_failure("Database records from MCP server were not a list.")
                return
            if not items:
                print_failure("Database records from MCP server were empty.")
                return
            titles = []
            for item in items:
                title = '"' + item.get("title", "") + '"'
                titles.append(title)
            display = ", ".join(titles)
            print_success("Database records from MCP server:", display)
        except Exception as error:
            print_failure("Database records from MCP server error:", error)
