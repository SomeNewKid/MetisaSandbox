"""Provide the tool which converts a document to Markdown."""

from __future__ import annotations

from typing import Annotated

import requests
from jsonschema import ValidationError, validate
from pydantic import Field

from .._helper import with_output_schema
from .._validation import validate_filename_argument

_DOCLING_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "markdown": {"type": "string"},
    },
    "required": ["markdown"],
    "additionalProperties": False,
}


@with_output_schema(_DOCLING_RESPONSE_SCHEMA)
def convert_document_to_markdown(
    filename: Annotated[str, Field(description="The filename of the document.")],
) -> dict[str, object]:
    """Return the Markdown for the content of the specified file."""
    _validate_arguments(filename)

    result = _execute_tool(filename)

    _validate_result(result)

    return result


def _validate_arguments(
    filename: str,
) -> None:
    validate_filename_argument(filename)


def _execute_tool(
    filename: str,
) -> dict[str, object]:
    docling_endpoint = "http://metisa-docling:8000/extract-markdown-from-document"
    headers = {
        "Accept": "application/json",
    }
    payload = {"filename": filename}

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                docling_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.json()
            response.raise_for_status()
            if not isinstance(content, dict):
                raise RuntimeError("Docling did not return JSON content.")
            return content
    except Exception as error:
        raise RuntimeError("Docling returned an error") from error


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, _DOCLING_RESPONSE_SCHEMA)
    except ValidationError as error:
        message = "Docling returned content in an unexpected format."
        raise RuntimeError(message) from error
