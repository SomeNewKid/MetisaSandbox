"""Provide the client which connects to the Prompt Guard sidecar."""

from __future__ import annotations

import requests
from jsonschema import ValidationError, validate

_PROMPT_GUARD_ENDPOINT = "http://metisa-prompt-guard:8000"

PROMPT_GUARD_CLASSIFICATION_SCHEMA = {
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


def classify_text(
    text: str,
) -> dict[str, object]:
    """Request and validate classification indicators from Prompt Guard."""
    endpoint = f"{_PROMPT_GUARD_ENDPOINT}/classify"

    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(
                endpoint,
                json={"text": text},
                headers={"Accept": "application/json"},
                timeout=(5, 240),
            )
            response.raise_for_status()
            content = response.json()

        validate(instance=content, schema=PROMPT_GUARD_CLASSIFICATION_SCHEMA)
    except (requests.RequestException, ValueError, ValidationError) as error:
        raise RuntimeError(
            "Prompt Guard classification could not be completed"
        ) from error

    if not isinstance(content, dict):
        raise RuntimeError("Prompt Guard returned an invalid response.")

    return content
