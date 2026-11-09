"""Provide the tool which screens user input."""

from __future__ import annotations

from typing import Annotated

from jsonschema import ValidationError, validate
from pydantic import Field

from metisa_common.clients.entity_guard_client import (
    ENTITY_GUARD_ANONYMIZE_SCHEMA,
    anonymize_text,
)
from metisa_common.clients.prompt_guard_client import (
    PROMPT_GUARD_CLASSIFICATION_SCHEMA,
    PROMPT_GUARD_MODERATION_SCHEMA,
    classify_text,
    moderate_text,
)
from metisa_common.utilities.type_models import (
    sanitize_content,
)

from .._helper import with_output_schema
from .._validation import validate_text_result

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
    sanitized_text = sanitize_content(text)
    if not sanitized_text.strip():
        return {
            "accept": False,
            "text": "",
            "reasons": ["empty_input"],
        }
    
    reasons: list[str] = []

    if _has_indicators(sanitized_text):
        reasons.append("prompt_guard_indicators")

    if _has_labels(sanitized_text):
        reasons.append("prompt_guard_labels")

    anonymized_text = ""
    try:
        anonymized_text = _anonymize_text(sanitized_text)
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
        error_message = "Screen user input tool returned an unexpected response."
        raise RuntimeError(error_message) from error

    texts = _get_texts_to_validate(result)
    for text in texts:
        validate_text_result(text)


def _get_texts_to_validate(
    result: dict[str, object],
) -> set[str]:
    texts_to_validate: list[str] = []

    text = result.get("text", None)
    if text is None:
        raise RuntimeError("Screen user input response in unexpected format.")
    if not isinstance(text, str):
        raise RuntimeError("Screen user input text in unexpected format.")

    if text.strip():
        texts_to_validate.append(text)

    reasons = result.get("reasons", None)
    if reasons is None:
        raise RuntimeError("Screen user input response in unexpected format.")
    if not isinstance(reasons, list):
        raise RuntimeError("Screen user input reasons in unexpected format.")

    for reason in reasons:
        if not isinstance(reason, str):
            raise RuntimeError("Screen user input reason in unexpected format.")
        if reason.strip():
            texts_to_validate.append(reason)

    return set(texts_to_validate)
