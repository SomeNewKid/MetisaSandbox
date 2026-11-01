"""Provide the tool which gets the title from a URL."""

from __future__ import annotations

from typing import Annotated

import requests
from jsonschema import ValidationError, validate
from pydantic import Field

from .._helper import with_output_schema
from .._validation import validate_url_argument

_TOOL_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
    },
    "required": ["title"],
    "additionalProperties": False,
}


@with_output_schema(_TOOL_RESULT_SCHEMA)
def get_title_from_url(
    url: Annotated[str, Field(description="The URL endpoint.")],
) -> dict[str, object]:
    """Return the title of the document at the specified URL."""
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
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        title = _parse_html_title(response.text)
        return {
            "title": title,
        }
    except Exception as error:
        raise RuntimeError(f"Could not get title from URL: {error}") from error


def _parse_html_title(response_text: str | None) -> str:
    if not response_text:
        return ""
    open_tag = "<title"
    open_tag_start = response_text.find(open_tag)
    if open_tag_start < 0:
        return ""
    open_tag_end = response_text.find(">", open_tag_start)
    if open_tag_end < 0:
        return ""
    close_tag = "</title>"
    close_tag_start = response_text.find(close_tag, open_tag_end)
    if close_tag_start < 0:
        return ""
    return response_text[open_tag_end + 1 : close_tag_start].strip()


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, _TOOL_RESULT_SCHEMA)
    except ValidationError as error:
        message = "Requests tool returned content in an unexpected format."
        raise RuntimeError(message) from error
