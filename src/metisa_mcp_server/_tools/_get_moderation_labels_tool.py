"""Provide the tool which gets moderation labels for the text."""

from __future__ import annotations

from typing import Annotated

from jsonschema import ValidationError, validate
from pydantic import Field

from .._clients._prompt_guard_client import (
    PROMPT_GUARD_MODERATION_SCHEMA,
    moderate_text,
)
from .._helper import with_output_schema


@with_output_schema(PROMPT_GUARD_MODERATION_SCHEMA)
def get_moderation_labels(
    text: Annotated[str, Field(description="The text to moderate")],
) -> dict[str, object]:
    """Return the classificatin of the provided text."""
    _validate_arguments(text)

    result = _execute_tool(text)

    _validate_result(result)

    return result


def _validate_arguments(
    text: str,
) -> None:
    if not text:
        raise ValueError("Text must be provided.")


def _execute_tool(
    text: str,
) -> dict[str, object]:
    return moderate_text(text)


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, PROMPT_GUARD_MODERATION_SCHEMA)
    except ValidationError as error:
        message = "Prompt Guard returned content in an unexpected format."
        raise RuntimeError(message) from error
