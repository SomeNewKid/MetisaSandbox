"""Provide the tool which gets content from a document."""

from __future__ import annotations

from typing import Annotated

import requests
from jsonschema import ValidationError, validate
from pydantic import Field

from .._helper import with_output_schema
from .._validation import validate_filename_argument, validate_text_result

_TOOL_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
    },
    "required": ["content"],
    "additionalProperties": False,
}


@with_output_schema(_TOOL_RESULT_SCHEMA)
def retrieve_content_from_document(
    filename: Annotated[str, Field(description="The filename of the document.")],
) -> dict[str, object]:
    """Return the data from the specified filename."""
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
    documents_endpoint = "http://metisa-documents:8080/"
    document_endpoint = f"{documents_endpoint}{filename}"
    headers = {}

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.get(
                document_endpoint,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Documents did not return any content")
        return {
            "content": content,
        }
    except Exception as error:
        if content:
            raise RuntimeError(f"Documents returned an error: {content}") from error
        raise RuntimeError(f"Documents returned an error: {error}") from error


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, _TOOL_RESULT_SCHEMA)
    except ValidationError as error:
        message = "Documents returned content in an unexpected format."
        raise RuntimeError(message) from error

    content = result.get("content", None)
    if content is None:
        raise RuntimeError("Documents response in unexpected format.")
    if not isinstance(content, str):
        raise RuntimeError("Documents content in unexpected format.")

    validate_text_result(content)
