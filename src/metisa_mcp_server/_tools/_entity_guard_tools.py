"""Provide the Entity Guard tools for the Metisa MCP Server."""

from __future__ import annotations

from typing import Annotated

import requests
from pydantic import Field

from .._helper import with_output_schema


@with_output_schema(
    {
        "type": "object",
        "properties": {
            "anonymized": {"type": "string"},
        },
        "required": ["anonymized"],
        "additionalProperties": False,
    }
)
def anonymize_text(
    text: Annotated[str, Field(description="The text to anonymize")],
) -> dict[str, object] | None:
    """Return the provided text with entities anonymized."""
    entity_guard_endpoint = "http://metisa-entity-guard:8000/anonymize"
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
                entity_guard_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.json()
            response.raise_for_status()
            if not isinstance(content, dict):
                raise RuntimeError("Entity Guard did not return JSON content.")
            return content
    except Exception as error:
        if content:
            raise RuntimeError(f"Entity Guard returned an error: {content}") from error
        raise RuntimeError(f"Entity Guard returned an error: {error}") from error
