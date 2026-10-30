"""Provide the internet tools for the Metisa MCP Server."""

from __future__ import annotations

import traceback
from typing import Annotated

import requests
from pydantic import Field

from .._helper import with_output_schema


@with_output_schema(
    {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
        },
        "required": ["title"],
        "additionalProperties": False,
    }
)
def get_title_from_url(
    url: Annotated[str, Field(description="The URL endpoint.")],
) -> dict[str, object] | None:
    """Return the title of the document at the specified URL."""
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


@with_output_schema(
    {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
        },
        "required": ["content"],
        "additionalProperties": False,
    }
)
def read_content_from_url(
    url: Annotated[str, Field(description="The URL endpoint.")],
) -> dict[str, object] | None:
    """Return plain text from a URL through the Jina Reader sidecar."""
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
