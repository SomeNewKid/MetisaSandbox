"""Test sanitization of Agent Memory JSON content."""

from __future__ import annotations

from copy import deepcopy

import pytest

from metisa_common.utilities.type_models import (
    JsonObject,
    JsonValue,
    sanitize_content,
    sanitize_json_object,
    sanitize_json_value,
)

_OWASP_CODE_POINTS = (
    *range(0xE0000, 0xE0080),
    *range(0xFE00, 0xFE10),
    0x200B,
    0x200C,
    0x200D,
    0x2060,
)

_PROHIBITED_CODE_POINTS = (
    *range(0xE0000, 0xE0080),
    *range(0xFE00, 0xFE10),
    0x200B,
    0x200C,
    0x200D,
    0x2060,
)


@pytest.mark.parametrize(
    "code_point",
    _OWASP_CODE_POINTS,
    ids=[f"U+{code_point:04X}" for code_point in _OWASP_CODE_POINTS],
)
def test_sanitize_content_removes_each_specified_character(code_point: int) -> None:
    character = chr(code_point)
    content = f"{character}before{character}after{character}"

    sanitized = sanitize_content(content)

    assert sanitized == "beforeafter"


def test_sanitize_content_removes_mixed_and_repeated_specified_characters() -> None:
    content = "\U000e0001Hello\u200b\u200b \ufe0fworld\u200c\u200d!\u2060\U000e007f"

    sanitized = sanitize_content(content)

    assert sanitized == "Hello world!"


def test_sanitize_content_removes_all_specified_characters_without_other_text() -> None:
    content = "".join(chr(code_point) for code_point in _OWASP_CODE_POINTS)

    sanitized = sanitize_content(content)

    assert sanitized == ""


@pytest.mark.parametrize(
    "content",
    [
        "",
        "Ordinary text, numbers 123, and punctuation!",
        "  Spaces\tand\nline breaks\r\n",
        (
            "Caf\u00e9, nai\u0308ve, \u4e2d\u6587, "
            "\u0645\u0631\u062d\u0628\u0627, \U0001f600"
        ),
        "\u200a\u200e\u205f\u2061\ufdff\ufe10\U000dffff\U000e0080",
    ],
    ids=["empty", "ascii", "whitespace", "unicode", "outside-specified-ranges"],
)
def test_sanitize_content_preserves_other_characters(content: str) -> None:
    sanitized = sanitize_content(content)

    assert sanitized == content


def test_sanitize_json_object_sanitizes_nested_dictionaries_and_lists() -> None:
    content: JsonObject = {
        "title": "Hel\u200blo",
        "details": {
            "message": "Wor\ufe0fld",
            "items": [
                "fir\u200cst",
                {"text": "sec\u200dond", "count": 3},
                ["thi\u2060rd", {"text": "\U000e0041fourth\U000e007f"}],
            ],
        },
    }
    expected: JsonObject = {
        "title": "Hello",
        "details": {
            "message": "World",
            "items": [
                "first",
                {"text": "second", "count": 3},
                ["third", {"text": "fourth"}],
            ],
        },
    }

    sanitized = sanitize_json_object(content)

    assert sanitized == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("a\u200bb\ufe0fc", "abc", id="string"),
        pytest.param("\u200b\U000e0001", "", id="only-prohibited-characters"),
        pytest.param({"text": "a\u200bb"}, {"text": "ab"}, id="dictionary"),
        pytest.param(
            ["a\u200bb", {"items": [["c\u2060d", None]]}],
            ["ab", {"items": [["cd", None]]}],
            id="nested-list-root",
        ),
        pytest.param({}, {}, id="empty-dictionary"),
        pytest.param([], [], id="empty-list"),
        pytest.param("", "", id="empty-string"),
        pytest.param(
            "Caf\u00e9 \U0001f600\n\t", "Caf\u00e9 \U0001f600\n\t", id="safe-text"
        ),
    ],
)
def test_sanitize_json_value_sanitizes_strings_in_containers(
    value: JsonValue,
    expected: JsonValue,
) -> None:
    sanitized = sanitize_json_value(value)

    assert sanitized == expected


@pytest.mark.parametrize("value", [None, True, False, 0, -7, 42, 0.0, -1.25])
def test_sanitize_json_value_preserves_non_string_values(value: JsonValue) -> None:
    sanitized = sanitize_json_value(value)

    assert sanitized == value
    assert type(sanitized) is type(value)


def test_sanitize_json_object_preserves_nested_non_string_values() -> None:
    content: JsonObject = {
        "nothing": None,
        "enabled": True,
        "disabled": False,
        "count": 7,
        "ratio": 0.25,
        "nested": {"values": [None, False, 0, 1.5]},
    }

    sanitized = sanitize_json_object(content)

    assert sanitized == content
    assert sanitized["enabled"] is True
    assert sanitized["disabled"] is False
    assert type(sanitized["count"]) is int
    assert type(sanitized["ratio"]) is float


def test_sanitize_json_object_accepts_empty_object() -> None:
    assert sanitize_json_object({}) == {}


def test_sanitize_json_object_preserves_safe_property_names() -> None:
    content: JsonObject = {"": "empty key", "caf\u00e9": "value", "two words": 2}

    assert sanitize_json_object(content) == content


@pytest.mark.parametrize(
    "code_point",
    _PROHIBITED_CODE_POINTS,
    ids=[f"U+{code_point:04X}" for code_point in _PROHIBITED_CODE_POINTS],
)
def test_sanitize_json_object_rejects_each_prohibited_character_in_keys(
    code_point: int,
) -> None:
    character = chr(code_point)
    content: JsonObject = {f"na{character}me": "value"}

    with pytest.raises(ValueError):
        sanitize_json_object(content)


@pytest.mark.parametrize(
    "content",
    [
        pytest.param({"\u200bname": "value"}, id="key-start"),
        pytest.param({"name\u200b": "value"}, id="key-end"),
        pytest.param({"\u200b": "value"}, id="entire-key"),
        pytest.param({"outer": {"na\u200bme": "value"}}, id="nested-dictionary"),
        pytest.param({"items": [{"na\u200bme": "value"}]}, id="dictionary-in-list"),
        pytest.param({"items": [[{"na\u200bme": "value"}]]}, id="nested-lists"),
        pytest.param({"name": 1, "na\u200bme": 2}, id="would-collide-after-removal"),
    ],
)
def test_sanitize_json_object_rejects_prohibited_keys_at_any_depth(
    content: JsonObject,
) -> None:
    with pytest.raises(ValueError):
        sanitize_json_object(content)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param({"na\u200bme": "value"}, id="dictionary-root"),
        pytest.param([{"na\u200bme": "value"}], id="list-root"),
        pytest.param([[{"outer": {"na\u200bme": "value"}}]], id="nested"),
    ],
)
def test_sanitize_json_value_rejects_prohibited_property_names(
    value: JsonValue,
) -> None:
    with pytest.raises(ValueError):
        sanitize_json_value(value)


def test_sanitization_does_not_modify_input_containers() -> None:
    content: JsonObject = {"items": ["a\u200bb", {"text": "c\u200dd"}]}
    original = deepcopy(content)

    sanitized_object = sanitize_json_object(content)
    sanitized_value = sanitize_json_value(content)

    assert sanitized_object == {"items": ["ab", {"text": "cd"}]}
    assert sanitized_value == sanitized_object
    assert content == original
