"""Provide the tool which greets the user."""

from __future__ import annotations

from typing import Annotated

from jsonschema import ValidationError, validate
from pydantic import Field

from .._helper import with_output_schema

_TOOL_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
    },
    "required": ["message"],
    "additionalProperties": False,
}


@with_output_schema(_TOOL_RESULT_SCHEMA)
def test_greeting_3(
    name: Annotated[str, Field(description="The name of the user")],
) -> dict[str, object]:
    """Return a test response."""
    _validate_arguments(name)

    result = _execute_tool(name)

    _validate_result(result)

    return result


def _validate_arguments(
    name: str,
) -> None:
    if not name:
        raise ValueError("Name must be provided.")


def _execute_tool(
    name: str,
) -> dict[str, object]:
    return {
        "message": f"Hello, {name}, from test_greeting_3.",
    }


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, _TOOL_RESULT_SCHEMA)
    except ValidationError as error:
        error_message = "Test greeting 3 tool returned content in an unexpected format."
        raise RuntimeError(error_message) from error
