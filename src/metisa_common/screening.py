"""Screen outbound MCP content before returning it to callers."""

from __future__ import annotations

import json

from metisa_common.clients.prompt_guard_client import classify_text

_MAX_DEPTH = 16
_MAX_NODES = 1024
_MAX_SCREENING_REQUEST_BYTES = 768 * 1024


class ScreeningError(RuntimeError):
    """Exception raised when screening fails."""


def screen_content(
    value: object,
) -> None:
    """Screen the given content for prompt injection indicators."""
    texts = _collect_texts(value)
    text = "\n".join(texts)

    if not text.strip():
        return

    request_payload = {"text": text}
    serialized_request = json.dumps(request_payload)
    request_bytes = serialized_request.encode("utf-8")

    if len(request_bytes) > _MAX_SCREENING_REQUEST_BYTES:
        raise ScreeningError("Content exceeds the screening size limit.")

    try:
        classification = classify_text(text)
    except RuntimeError as error:
        raise ScreeningError("Content screening is unavailable.") from error

    if classification["indicators"]:
        raise ScreeningError("Content was blocked by prompt injection screening.")


def _collect_texts(
    value: object,
) -> list[str]:
    texts: list[str] = []
    pending: list[tuple[object, int]] = [(value, 0)]
    visited_nodes = 0

    while pending:
        current, depth = pending.pop()
        visited_nodes += 1

        if depth > _MAX_DEPTH or visited_nodes > _MAX_NODES:
            raise ScreeningError("Content exceeds the screening structure limit.")

        if isinstance(current, str):
            texts.append(current)
            continue

        if current is None or type(current) in (bool, int, float):
            continue

        if isinstance(current, dict):
            children: list[object] = []

            for key, item in current.items():
                if not isinstance(key, str):
                    raise ScreeningError("Content contains a non-string key.")

                children.append(key)
                children.append(item)

        elif isinstance(current, list):
            children = current

        else:
            raise ScreeningError("Content contains an unsupported value.")

        for child in reversed(children):
            pending.append((child, depth + 1))

    return texts
