"""Code Execution tests for the sample agent."""

from __future__ import annotations

from textwrap import dedent

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

_SKIP_CODE_EXECUTION_TESTS = False


def test_code_execution(specification: MetisaSpecification):
    """Run code execution tests."""
    print_suite_title("Code Execution")

    if _SKIP_CODE_EXECUTION_TESTS:
        print_caution("Code execution capability is being skipped.")
        return

    if Capability.CODE_EXECUTION not in specification.capabilities:
        print_disabled("Code execution capability not declared.")
        return

    with print_elapsed_time():
        try:
            code = dedent(
                """
                def main():
                    values = [10, 20, 30]
                    total = 0
                    for value in values:
                        total += value
                    return total / len(values)
                """
            )
            code_execution_result = get_mcp_server_tool_result(
                tool_name="execute_starlark_code",
                params={"starlark_code": code},
            )
            print_success("Code execution result:", code_execution_result)
        except Exception as error:
            print_failure("Code execution error:", error)
