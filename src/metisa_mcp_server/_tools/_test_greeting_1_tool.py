"""Provide the tool which greets the user."""

from __future__ import annotations

from jsonschema import ValidationError, validate

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
def test_greeting_1() -> dict[str, object]:
    """Return a test response."""
    _validate_arguments()

    result = _execute_tool()

    _validate_result(result)

    return result


def _validate_arguments() -> None:
    pass


def _execute_tool() -> dict[str, object]:
    return {
        "message": "Hello, from test_greeting_1.",
    }


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, _TOOL_RESULT_SCHEMA)
    except ValidationError as error:
        error_message = "Test greeting 1 tool returned content in an unexpected format."
        raise RuntimeError(error_message) from error
