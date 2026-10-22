"""Utility functions for detecting prompt injection attacks."""

from __future__ import annotations

import base64
import unicodedata
from collections.abc import Callable

from unidecode import unidecode

# Some functions based on the OWASP LLM Prompt Injection Prevention Cheat Sheet
# https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html


def get_normalized_words(
    text: str,
) -> list[str]:
    """Return the normalized words in the provided text."""
    text = _replace_unicode_tags(text)
    words = text.split()
    words = _expand_words(words, expand_base64_encoded_text)
    words = _expand_words(words, expand_hex_encoded_text)

    normalized_words: list[str] = []

    for word in words:
        normalized_word = normalize_word(word)
        if normalize_word:
            normalized_words.append(normalized_word)

    return normalized_words


def is_typoglycemia_variant(
    word: str,
    target: str,
) -> bool:
    """Return if the word is a typoglycemia variant of the target."""
    # A typoglycemia variant means the same first and last letter,
    # with scrambled middle letters, such as "ignore" and "ingore".

    word = normalize_word(word)
    target = normalize_word(target)

    if len(word) != len(target):
        return False

    if len(word) <= 3:
        return False

    if word[0] != target[0]:
        return False

    if word[-1] != target[-1]:
        return False

    return sorted(word[1:-1]) == sorted(target[1:-1])


def normalize_word(
    word: str,
) -> str:
    """Return the normalized form of the word."""
    normalized = _replace_unicode_tags(word)
    normalized = normalized.strip().lower()
    normalized = _remove_diacritics(normalized)
    normalized = _remove_transliteration(normalized).lower()
    normalized = _remove_non_letters(normalized)
    return normalized


def expand_base64_encoded_text(
    text: str,
) -> str:
    """Return the decoded form of the Base64 encoded text."""
    try:
        decoded_bytes = base64.b64decode(text)
        return decoded_bytes.decode("utf-8")
    except Exception:
        return text


def expand_hex_encoded_text(
    text: str,
) -> str:
    """Return the decoded form of the Hex encoded text."""
    try:
        decoded_bytes = bytes.fromhex(text)
        return decoded_bytes.decode("utf-8")
    except Exception:
        return text


def _expand_words(
    words: list[str],
    decoder: Callable[[str], str],
) -> list[str]:
    expanded_words: list[str] = []
    for word in words:
        decoded_text = decoder(word)
        decoded_words = decoded_text.split()
        expanded_words.extend(decoded_words)

    return expanded_words


def _remove_diacritics(
    word: str,
) -> str:
    # Normalize string to decompose characters (e.g., 'é' becomes 'e' + '´')
    normalized = unicodedata.normalize("NFD", word)

    # Filter out the combining diacritic marks (category 'Mn')
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


# "Førget" → "Forget"
def _remove_transliteration(
    word: str,
) -> str:
    return unidecode(word)


def _remove_non_letters(
    word: str,
) -> str:
    return "".join(char for char in word if "a" <= char <= "z" or "A" <= char <= "Z")


def _replace_unicode_tags(
    text: str,
) -> str:
    characters: list[str] = []

    for character in text:
        code_point = ord(character)
        if 0xE0020 <= code_point <= 0xE007E:
            character = chr(code_point - 0xE0000)
        characters.append(character)

    return "".join(characters)
