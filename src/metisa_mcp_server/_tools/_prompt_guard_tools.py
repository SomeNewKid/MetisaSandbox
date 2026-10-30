"""Provide the Prompt Guard tools for the Metisa MCP Server."""

from __future__ import annotations

from typing import Annotated

import requests
from pydantic import Field

from .._helper import with_output_schema


@with_output_schema(
    {
        "type": "object",
        "properties": {
            "indicators": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "check_id": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["check_id", "explanation"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["indicators"],
        "additionalProperties": False,
    }
)
def classify_text(
    text: Annotated[str, Field(description="The text to classify")],
) -> dict[str, object] | None:
    """Return the classificatin of the provided text."""
    prompt_guard_endpoint = "http://metisa-prompt-guard:8000/classify"
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


@with_output_schema(
    {
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
)
def moderate_text(
    text: Annotated[str, Field(description="The text to moderate")],
) -> dict[str, object] | None:
    """Return the classificatin of the provided text."""
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
