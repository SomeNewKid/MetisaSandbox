"""Database tests for the sample agent."""

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


def test_database_access(specification: MetisaSpecification):
    """Run database access tests."""
    print_suite_title("Database")

    if Capability.LOCALNET not in specification.capabilities:
        print_skipped("Localnet capability not declared.")
        return

    with print_elapsed_time():
        try:
            active_items = get_mcp_server_tool_result(
                tool_name="get_active_items",
            )
            print_success("Database records from MCP server:", active_items)
        except Exception as error:
            print_failure("Database records from MCP server error:", error)
