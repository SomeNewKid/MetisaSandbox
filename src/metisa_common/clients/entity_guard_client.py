"""Provide the client which connects to the Entity Guard sidecar."""

from __future__ import annotations

import requests
from jsonschema import ValidationError, validate

_ENTITY_GUARD_ENDPOINT = "http://metisa-entity-guard:8000"

ENTITY_GUARD_ANONYMIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "anonymized": {"type": "string"},
    },
    "required": ["anonymized"],
    "additionalProperties": False,
}


def anonymize_text(
    text: str,
) -> dict[str, object]:
    """Request and validate classification indicators from Entity Guard."""
    endpoint = f"{_ENTITY_GUARD_ENDPOINT}/anonymize"

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

        validate(instance=content, schema=ENTITY_GUARD_ANONYMIZE_SCHEMA)
    except (requests.RequestException, ValueError, ValidationError) as error:
        raise RuntimeError(
            "Entity Guard anonymization could not be completed."
        ) from error

    if not isinstance(content, dict):
        raise RuntimeError("Entity Guard returned an invalid response.")

    return content
