"""Models for validatd and sanitized types."""

from __future__ import annotations

import math
from typing import TypeAlias

JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)

JsonObject: TypeAlias = dict[str, JsonValue]


def validate_json_object(
    value: object,
    *,
    name: str = "value",
) -> None:
    """Raise error if value is not a valid JSON object."""
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dictionary.")

    active_containers: set[int] = set()
    _validate_json_value(value, name, active_containers)


def sanitize_content(
    value: str,
) -> str:
    """Sanitize the given content by removing potentially dangerous elements."""
    zero_width_code_points = {
        0x200B,  # Zero Width Space
        0x200C,  # Zero Width Non-Joiner
        0x200D,  # Zero Width Joiner
        0x2060,  # Word Joiner
    }

    retained_characters: list[str] = []

    for character in value:
        code_point = ord(character)

        # Unicode tags block
        if 0xE0000 <= code_point <= 0xE007F:
            continue

        # Variation Selectors
        if 0xFE00 <= code_point <= 0xFE0F:
            continue

        if code_point in zero_width_code_points:
            continue

        retained_characters.append(character)

    return "".join(retained_characters)


def sanitize_json_object(
    value: JsonObject,
) -> JsonObject:
    """Sanitize the string properties of the specified JSON object."""
    sanitized: JsonObject = {}

    for key, item in value.items():
        sanitized_key = sanitize_content(key)

        if sanitized_key != key:
            error_message = "JSON property names must not contain prohibited characters"
            raise ValueError(error_message)

        sanitized_item = sanitize_json_value(item)
        sanitized[key] = sanitized_item

    return sanitized


def sanitize_json_value(
    value: JsonValue,
) -> JsonValue:
    """Sanitize the string properties of the specified JSON value."""
    if isinstance(value, str):
        return sanitize_content(value)

    if isinstance(value, dict):
        return sanitize_json_object(value)

    if isinstance(value, list):
        sanitized_items: list[JsonValue] = []

        for item in value:
            sanitized_item = sanitize_json_value(item)
            sanitized_items.append(sanitized_item)

        return sanitized_items

    return value


def _validate_json_value(
    value: object,
    path: str,
    active_containers: set[int],
) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must not contain NaN or infinity.")
        return

    if not isinstance(value, (list, dict)):
        value_type = type(value).__name__
        raise TypeError(f"{path} contains an unsupported JSON type: {value_type}.")

    container_id = id(value)
    if container_id in active_containers:
        raise ValueError(f"{path} contains a circular reference.")

    active_containers.add(container_id)

    try:
        if isinstance(value, list):
            for index, item in enumerate(value):
                item_path = f"{path}[{index}]"
                _validate_json_value(item, item_path, active_containers)
        else:
            for key, item in value.items():
                if not isinstance(key, str):
                    error = f"{path} contains a dictionary key that is not a string."
                    raise TypeError(error)

                item_path = f"{path}[{key!r}]"
                _validate_json_value(item, item_path, active_containers)

    finally:
        active_containers.remove(container_id)
