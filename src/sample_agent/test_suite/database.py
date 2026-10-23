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
            active_items = get_mcp_server_tool_result(
                tool_name="get_active_items",
            )
            print_success("Database records from MCP server:", active_items)
        except Exception as error:
            print_failure("Database records from MCP server error:", error)
