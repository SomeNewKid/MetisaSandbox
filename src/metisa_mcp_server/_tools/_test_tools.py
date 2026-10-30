"""Provide the test tools for the Metisa MCP Server."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from .._helper import with_output_schema

_GREETING_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
    },
    "required": ["message"],
    "additionalProperties": False,
}


@with_output_schema(_GREETING_OUTPUT_SCHEMA)
def test_tool_1() -> dict[str, object]:
    """Return a test response."""
    return {
        "message": "Hello, from test_tool_1.",
    }


@with_output_schema(_GREETING_OUTPUT_SCHEMA)
def test_tool_2(
    name: Annotated[str, Field(description="The name of the user")],
) -> dict[str, object]:
    """Return a test response."""
    if not name:
        return {
            "message": "Hello, from test_tool_2.",
        }
    return {
        "message": f"Hello, {name}, from test_tool_2.",
    }


@with_output_schema(_GREETING_OUTPUT_SCHEMA)
def test_tool_3(
    name: Annotated[str, Field(description="The name of the user")],
) -> dict[str, object]:
    """Return a test response."""
    if not name:
        raise ValueError("Name must be provided for test_tool_3.")
    return {
        "message": f"Hello, {name}, from test_tool_3.",
    }
