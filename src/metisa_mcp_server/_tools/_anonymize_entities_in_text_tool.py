"""Provide the tool which anonymizes entities in text."""

from __future__ import annotations

from typing import Annotated

from jsonschema import ValidationError, validate
from pydantic import Field

from .._clients._entity_guard_client import (
    ENTITY_GUARD_ANONYMIZE_SCHEMA,
    anonymize_text,
)
from .._helper import with_output_schema


@with_output_schema(ENTITY_GUARD_ANONYMIZE_SCHEMA)
def anonymize_entities_in_text(
    text: Annotated[str, Field(description="The text to anonymize")],
) -> dict[str, object]:
    """Return the provided text with entities anonymized."""
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
    return anonymize_text(text)


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, ENTITY_GUARD_ANONYMIZE_SCHEMA)
    except ValidationError as error:
        message = "Entity Guard returned content in an unexpected format."
        raise RuntimeError(message) from error
