"""Provide the tool which uses semantic search to get chunks from a document."""

from __future__ import annotations

from typing import Annotated

import requests
from jsonschema import ValidationError, validate
from pydantic import Field

from .._helper import with_output_schema
from .._validation import validate_filename_argument

_TOOL_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "chunks": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["chunks"],
    "additionalProperties": False,
}


@with_output_schema(_TOOL_RESULT_SCHEMA)
def get_semantic_chunks_from_document(
    filename: Annotated[str, Field(description="The filename of the document.")],
    prompt: Annotated[str, Field(description="The user's prompt.")],
) -> dict[str, object]:
    """Return the chunks from the specified file."""
    _validate_arguments(filename, prompt)

    result = _execute_tool(filename, prompt)

    _validate_result(result)

    return result


def _validate_arguments(
    filename: str,
    prompt: str,
) -> None:
    validate_filename_argument(filename)
    if not prompt:
        raise ValueError("Prompt must be provided.")


def _execute_tool(
    filename: str,
    prompt: str,
) -> dict[str, object]:
    embeddings_endpoint = "http://metisa-embeddings:8000/search"
    headers = {
        "Accept": "application/json",
    }
    payload = {
        "filename": filename,
        "prompt": prompt,
    }

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                embeddings_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.json()
            response.raise_for_status()
            if not isinstance(content, dict):
                raise RuntimeError("Embeddings did not return JSON content")
            return content
    except Exception as error:
        raise RuntimeError("Embeddings returned an error.") from error


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, _TOOL_RESULT_SCHEMA)
    except ValidationError as error:
        message = "Embeddings returned content in an unexpected format."
        raise RuntimeError(message) from error
