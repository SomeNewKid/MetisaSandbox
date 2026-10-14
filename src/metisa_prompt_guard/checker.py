"""Run a series of checks for prompt injection risks."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .checks.direct_prompt_injections import (
    has_attempt_to_change_authority_in_normalized_words,
    has_attempt_to_ignore_instructions_in_normalized_words,
    has_attempt_to_reveal_system_prompt_in_normalized_words,
)
from .helper import get_normalized_words
from .models import Indicator

CheckFunction = Callable[[Sequence[str]], Indicator | None]

_CHECKS: tuple[CheckFunction, ...] = (
    has_attempt_to_change_authority_in_normalized_words,
    has_attempt_to_ignore_instructions_in_normalized_words,
    has_attempt_to_reveal_system_prompt_in_normalized_words,
)


def run_checks(
    text: str,
) -> tuple[Indicator, ...]:
    """Run heuristic checks on the provided text."""
    chunks: list[Sequence[str]] = _get_chunks_from_text(text)
    indicators: list[Indicator] = []

    for chunk in chunks:
        indicators.extend(_run_checks_on_chunk(chunk))

    return tuple(indicators)


def _run_checks_on_chunk(
    words_in_chunk: Sequence[str],
) -> tuple[Indicator, ...]:
    indicators: list[Indicator] = []

    if words_in_chunk:
        for check in _CHECKS:
            indicator = check(words_in_chunk)
            if indicator is not None:
                indicators.append(indicator)

    return tuple(indicators)


def _get_chunks_from_text(
    text: str,
) -> list[Sequence[str]]:
    normalized_words = get_normalized_words(text)
    chunks: list[Sequence[str]] = []

    chunk_size = 30
    overlap = 10
    step = chunk_size - overlap
    num_normalized_words = len(normalized_words)

    for start in range(0, num_normalized_words, step):
        end = start + chunk_size
        chunk = normalized_words[start:end]
        chunks.append(chunk)

        if end >= num_normalized_words:
            break

    return chunks
