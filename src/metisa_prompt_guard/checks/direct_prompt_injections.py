"""Heuristic checks for direct prompt injections."""

from __future__ import annotations

from collections.abc import Sequence

from ..helper import get_normalized_words, is_typoglycemia_variant
from ..models import Indicator

# Based on the OWASP LLM Prompt Injection Prevention Cheat Sheet
# https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html

# These checks are not intended to be comprehensive or foolproof.
# They are simple heuristics to complement the model-based checks.


def has_attempt_to_ignore_instructions(
    text: str,
) -> Indicator | None:
    """Check text for an attempt to ignore instructions."""
    normalized_words = get_normalized_words(text)
    return has_attempt_to_ignore_instructions_in_normalized_words(normalized_words)


def has_attempt_to_ignore_instructions_in_normalized_words(
    sequenced_words: Sequence[str],
) -> Indicator | None:
    """Check normalized words for an attempt to ignore instructions."""
    check_id = "instruction_overrides__has_attempt_to_ignore_instructions"
    explanation = "The text contains an attempt to ignore previous instructions."

    # create mutable list
    normalized_words: list[str] = _create_list_from_sequence(sequenced_words)

    if not normalized_words:
        return None

    standardized_words: list[str] = []
    for normalized_word in normalized_words:
        standardized_word = _standardize_for_attempt_to_ignore_instructions(
            normalized_word
        )
        if standardized_word:
            standardized_words.append(standardized_word)

    if _phrase_is_in_words(("ignore", "previous", "instructions"), standardized_words):
        return Indicator(check_id, explanation)

    return None


def has_attempt_to_change_authority(
    text: str,
) -> Indicator | None:
    """Check text for an attempt to change authority."""
    normalized_words = get_normalized_words(text)
    return has_attempt_to_change_authority_in_normalized_words(normalized_words)


def has_attempt_to_change_authority_in_normalized_words(
    sequenced_words: Sequence[str],
) -> Indicator | None:
    """Check normalized words for an attempt to change authority."""
    check_id = "instruction_overrides__has_attempt_to_change_authority"
    explanation = "The text contains an attempt to change authority."

    # create mutable list
    normalized_words: list[str] = _create_list_from_sequence(sequenced_words)

    if not normalized_words:
        return None

    _replace_phrase_in_words(normalized_words, ("you", "are"), ("change",))
    _replace_phrase_in_words(normalized_words, ("you", "now", "are"), ("change",))

    standardized_words: list[str] = []
    for normalized_word in normalized_words:
        standardized_word = _standardize_for_attempt_to_change_authority(
            normalized_word
        )
        if standardized_word:
            standardized_words.append(standardized_word)

    has_change_word = "change" in standardized_words

    has_authority_signal = _phrase_is_in_words(
        ("developer", "mode"), standardized_words
    )

    if has_change_word and has_authority_signal:
        return Indicator(check_id, explanation)

    return None


def has_attempt_to_reveal_system_prompt(
    text: str,
) -> Indicator | None:
    """Check text for an attempt to reveal the system prompt."""
    normalized_words = get_normalized_words(text)
    return has_attempt_to_reveal_system_prompt_in_normalized_words(normalized_words)


def has_attempt_to_reveal_system_prompt_in_normalized_words(
    sequenced_words: Sequence[str],
) -> Indicator | None:
    """Check text for an attempt to reveal the system prompt."""
    check_id = "instruction_overrides__has_attempt_to_reveal_system_prompt"
    explanation = "The text contains an attempt to reveal the system prompt."

    # create mutable list
    normalized_words: list[str] = _create_list_from_sequence(sequenced_words)

    if not normalized_words:
        return None

    standardized_words: list[str] = []
    for normalized_word in normalized_words:
        standardized_word = _standardize_for_attempt_to_reveal_prompt(normalized_word)
        if standardized_word:
            standardized_words.append(standardized_word)

    has_reveal_word = "reveal" in standardized_words
    has_system_prompt_phrase = _phrase_is_in_words(
        ("system", "prompt"),
        standardized_words,
    )

    if has_reveal_word and has_system_prompt_phrase:
        return Indicator(check_id, explanation)

    return None


def _create_list_from_sequence(
    sequence: Sequence[str],
) -> list[str]:
    collection: list[str] = []
    for item in sequence:
        collection.append(item)
    return collection


def _replace_phrase_in_words(
    words: list[str],
    target: tuple[str, ...],
    replacement: tuple[str, ...],
) -> None:
    target_length = len(target)
    i = 0
    while i <= len(words) - target_length:
        if tuple(words[i : i + target_length]) == target:
            words[i : i + target_length] = list(replacement)
            i += len(replacement)
        else:
            i += 1


def _phrase_is_in_words(
    phrase: tuple[str, ...],
    words: list[str],
) -> bool:
    phrase_length = len(phrase)
    for i in range(len(words) - phrase_length + 1):
        if tuple(words[i : i + phrase_length]) == phrase:
            return True
    return False


def _standardize_for_attempt_to_ignore_instructions(
    word: str,
) -> str:
    standardized = "ignore"
    candidates = (
        "ignore",
        "bypass",
        "override",
        "skip",
        "disregard",
        "forget",
    )
    if _is_word_in_candidates(word, candidates):
        return standardized

    standardized = "instructions"
    candidates = (
        "instruction",
        "instructions",
        "guideline",
        "guidelines",
        "rule",
        "rules",
        "directive",
        "directives",
        "command",
        "commands",
    )
    if _is_word_in_candidates(word, candidates):
        return standardized

    standardized = "previous"
    candidates = (
        "previous",
        "earlier",
        "prior",
    )
    if _is_word_in_candidates(word, candidates):
        return standardized

    standardized = ""
    candidates = (
        "all",
        "every",
        "each",
        "any",
        "my",
    )
    if _is_word_in_candidates(word, candidates):
        return standardized

    return word


def _standardize_for_attempt_to_change_authority(
    word: str,
) -> str:
    standardized = "change"
    candidates = (
        "change",
        "switch",
        "enter",
        "activate",
    )
    if _is_word_in_candidates(word, candidates):
        return standardized

    standardized = "developer"
    candidates = (
        "developer",
        "dev",
        "admin",
        "administrator",
        "root",
        "superuser",
        "elevated",
    )
    if _is_word_in_candidates(word, candidates):
        return standardized

    standardized = "mode"
    candidates = (
        "mode",
        "role",
        "user",
    )
    if _is_word_in_candidates(word, candidates):
        return standardized

    standardized = ""
    candidates = (
        "to",
        "into",
        "the",
        "a",
        "an",
    )
    if _is_word_in_candidates(word, candidates):
        return standardized

    return word


def _standardize_for_attempt_to_reveal_prompt(
    word: str,
) -> str:
    standardized = "reveal"
    candidates = (
        "reveal",
        "show",
        "print",
        "display",
    )
    if _is_word_in_candidates(word, candidates):
        return standardized

    standardized = "prompt"
    candidates = (
        "prompt",
        "instruction",
        "instructions",
    )
    if _is_word_in_candidates(word, candidates):
        return standardized

    return word


def _is_word_in_candidates(
    word: str,
    candidates: tuple[str, ...],
) -> bool:
    for candidate in candidates:
        if _is_word_or_typoglycemia_variant(word, candidate):
            return True
    return False


def _is_word_or_typoglycemia_variant(
    word: str,
    target: str,
) -> bool:
    if word == target:
        return True
    if is_typoglycemia_variant(word, target):
        return True
    return False
