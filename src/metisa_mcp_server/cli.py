"""Command-line interface for the Metisa MCP Server module."""

from __future__ import annotations

import sys


def main(
    argv: list[str] | None = None,
) -> int:
    """Run the Metisa probes."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("Error: no tool or resource argument.", file=sys.stderr)
        return 1

    tool, resource = _get_requested_tool_or_resource(args)
    if not tool and not resource:
        print("Error: no tool or resource argument.", file=sys.stderr)
        return 1

    print("Hello, world!")
    print("Tool:", tool)
    print("Resource", resource)

    return 0


def _get_requested_tool_or_resource(
    args: list[str],
) -> tuple[str, str]:
    requested_tool = ""
    requested_resource = ""
    if not args:
        return requested_tool, requested_resource

    if args[0] == "--tool":
        requested_tool = args[1] if len(args) > 1 else ""
    elif args[0] == "--resource":
        requested_resource = args[1] if len(args) > 1 else ""

    return requested_tool, requested_resource
