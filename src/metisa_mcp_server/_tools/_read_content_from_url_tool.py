"""Provide the tool which gets content from a URL."""

from __future__ import annotations

import traceback
from typing import Annotated

import requests
from jsonschema import ValidationError, validate
from pydantic import Field

from .._helper import with_output_schema
from .._validation import validate_text_result, validate_url_argument

_TOOL_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
    },
    "required": ["content"],
    "additionalProperties": False,
}


@with_output_schema(_TOOL_RESULT_SCHEMA)
def read_content_from_url(
    url: Annotated[str, Field(description="The URL endpoint.")],
) -> dict[str, object]:
    """Return plain text from a URL through the Jina Reader sidecar."""
    _validate_arguments(url)

    result = _execute_tool(url)

    _validate_result(result)

    return result


def _validate_arguments(
    url: str,
) -> None:
    validate_url_argument(url)


def _execute_tool(
    url: str,
) -> dict[str, object]:
    reader_endpoint = "http://metisa-jina-reader:8081/"
    headers = {
        "Accept": "text/plain",
        "X-Respond-With": "text",
        "X-Engine": "browser",
    }
    payload = {"url": url}

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                reader_endpoint,
                data=payload,
                headers=headers,
                timeout=(5, 60),
            )
            content = response.text
            response.raise_for_status()
        return {
            "content": content,
        }
    except requests.RequestException as error:
        error_message = f"Jina Reader could not read the url: {error}"
        raise RuntimeError(error_message) from error
    except Exception as error:
        traceback.print_exception(error)
        error_message = f"Jina Reader could not read the url: {error}"
        raise RuntimeError(error_message) from error


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, _TOOL_RESULT_SCHEMA)
    except ValidationError as error:
        message = "Jina Reader returned content in an unexpected format."
        raise RuntimeError(message) from error

    content = result.get("content", None)
    if content is None:
        raise RuntimeError("Jina Reader response in unexpected format.")
    if not isinstance(content, str):
        raise RuntimeError("Jina Reader content in unexpected format.")

    validate_text_result(content)
