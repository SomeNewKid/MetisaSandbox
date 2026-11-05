"""Provide the tool which screens user input."""

from __future__ import annotations

from typing import Annotated

from jsonschema import ValidationError, validate
from pydantic import Field

from .._clients._entity_guard_client import (
    ENTITY_GUARD_ANONYMIZE_SCHEMA,
    anonymize_text,
)
from .._clients._prompt_guard_client import (
    PROMPT_GUARD_CLASSIFICATION_SCHEMA,
    PROMPT_GUARD_MODERATION_SCHEMA,
    classify_text,
    moderate_text,
)
from .._helper import with_output_schema

_TOOL_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "accept": {"type": "boolean"},
        "text": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["accept", "text", "reasons"],
    "additionalProperties": False,
}


@with_output_schema(_TOOL_RESULT_SCHEMA)
def screen_user_input(
    text: Annotated[str, Field(description="The text to screen")],
) -> dict[str, object]:
    """Return the user input after screening."""
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
    reasons: list[str] = []
    if not text.strip():
        return {
            "accept": True,
            "text": text,
            "reasons": reasons,
        }

    if _has_indicators(text):
        reasons.append("prompt_guard_indicators")

    if _has_labels(text):
        reasons.append("prompt_guard_labels")

    anonymized_text = ""
    try:
        anonymized_text = _anonymize_text(text)
    except Exception:
        reasons.append("entity_guard_anonymize_failed")

    accept = not reasons
    if accept:
        text = anonymized_text
    else:
        text = ""

    return {
        "accept": accept,
        "text": text,
        "reasons": reasons,
    }


def _has_indicators(
    text: str,
) -> bool:
    classification_json = classify_text(text)
    validate(classification_json, PROMPT_GUARD_CLASSIFICATION_SCHEMA)
    indicators = classification_json.get("indicators", [])
    if indicators:
        return True
    return False


def _has_labels(
    text: str,
) -> bool:
    moderation_json = moderate_text(text)
    validate(moderation_json, PROMPT_GUARD_MODERATION_SCHEMA)
    labels = moderation_json.get("labels", [])
    if labels:
        return True
    return False


def _anonymize_text(
    text: str,
) -> str:
    anonymize_json = anonymize_text(text)
    validate(anonymize_json, ENTITY_GUARD_ANONYMIZE_SCHEMA)
    anonymized_text = anonymize_json.get("anonymized", None)
    if anonymized_text is None:
        raise ValueError("Anonymized text not found in response.")
    if not isinstance(anonymized_text, str):
        raise ValueError("Anonymized text is not a string.")
    return anonymized_text


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, _TOOL_RESULT_SCHEMA)
    except ValidationError as error:
        message = "Screen user input tool returned content in an unexpected format."
        raise RuntimeError(message) from error
