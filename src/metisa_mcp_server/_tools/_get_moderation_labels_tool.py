"""Provide the tool which gets moderation labels for the text."""

from __future__ import annotations

from typing import Annotated

import requests
from jsonschema import ValidationError, validate
from pydantic import Field

from .._helper import with_output_schema

_TOOL_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["labels"],
    "additionalProperties": False,
}


@with_output_schema(_TOOL_RESULT_SCHEMA)
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
    prompt_guard_endpoint = "http://metisa-prompt-guard:8000/moderate"
    headers = {
        "Accept": "application/json",
    }
    payload = {"text": text}

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                prompt_guard_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.json()
            response.raise_for_status()
            if not isinstance(content, dict):
                raise RuntimeError("Prompt Guard did not return JSON content.")
            return content
    except Exception as error:
        if content:
            raise RuntimeError(f"Prompt Guard returned an error: {content}") from error
        raise RuntimeError(f"Prompt Guard returned an error: {error}") from error


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, _TOOL_RESULT_SCHEMA)
    except ValidationError as error:
        message = "Prompt Guard returned content in an unexpected format."
        raise RuntimeError(message) from error
