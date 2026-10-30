"""Provide the document tools for the Metisa MCP Server."""

from __future__ import annotations

from typing import Annotated

import requests
from pydantic import Field

from .._helper import with_output_schema


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
def retrieve_from_documents(
    filename: Annotated[str, Field(description="The filename of the document.")],
) -> dict[str, object] | None:
    """Return the data from the specified filename."""
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


@with_output_schema(
    {
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
)
def get_matching_chunks(
    filename: Annotated[str, Field(description="The filename of the document.")],
    prompt: Annotated[str, Field(description="The user's prompt.")],
) -> dict[str, object] | None:
    """Return the data from the specified filename."""
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
        if content:
            raise RuntimeError(f"Embeddings returned an error: {content}") from error
        raise RuntimeError(f"Embeddings returned an error: {error}") from error
