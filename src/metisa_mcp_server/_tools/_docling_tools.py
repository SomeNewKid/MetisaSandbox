"""Provide the Docling tools for the Metisa MCP Server."""

from __future__ import annotations

from typing import Annotated

import requests
from pydantic import Field

from .._helper import with_output_schema


@with_output_schema(
    {
        "type": "object",
        "properties": {
            "markdown": {"type": "string"},
        },
        "required": ["markdown"],
        "additionalProperties": False,
    }
)
def extract_markdown_from_document(
    filename: Annotated[str, Field(description="The filename of the sample.")],
) -> dict[str, object] | None:
    """Return the data from the specified example filename."""
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
        if content:
            raise RuntimeError(f"Docling returned an error: {content}") from error
        raise RuntimeError(f"Docling returned an error: {error}") from error
