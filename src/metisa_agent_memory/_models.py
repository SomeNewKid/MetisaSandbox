"""Models for episodic and semantic agent memory."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias
from uuid import UUID

JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)

JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass
class Episode:
    """Represent an episode."""

    id: UUID | None
    namespace: str
    agent_id: str | None
    run_id: str | None
    trace_id: str | None
    kind: str
    content: JsonObject
    metadata: JsonObject
    created_at: datetime | None
    expires_at: datetime | None

    def validate(self) -> None:
        """Validate the current Episode."""
        _validate_id(self.id)
        _validate_namespace(self.namespace)
        _validate_identifier(self.agent_id, name="agent_id")
        _validate_identifier(self.run_id, name="run_id")
        _validate_identifier(self.trace_id, name="trace_id")
        _validate_string(self.kind, name="kind")
        validate_json_object(self.content, name="content")
        validate_json_object(self.metadata, name="metadata")
        _validate_datetime(self.created_at, name="created_at")
        _validate_datetime(self.expires_at, name="expires_at")


@dataclass
class Memory:
    """Represent a memory."""

    id: UUID | None
    namespace: str
    subject: str
    content: JsonObject
    text: str
    embedding: list[float]
    metadata: JsonObject
    valid_to: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    expires_at: datetime | None

    def validate(self) -> None:
        """Validate the current Memory."""
        _validate_id(self.id)
        _validate_namespace(self.namespace)
        _validate_string(self.subject, name="subject")
        _validate_string(self.text, name="text")
        _validate_embedding(self.embedding)
        validate_json_object(self.content, name="content")
        validate_json_object(self.metadata, name="metadata")
        _validate_datetime(self.valid_to, name="valid_to")
        _validate_datetime(self.created_at, name="created_at")
        _validate_datetime(self.updated_at, name="updated_at")
        _validate_datetime(self.expires_at, name="expires_at")


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


def _validate_id(
    id: object,
) -> None:
    if not isinstance(id, (UUID, type(None))):
        raise TypeError("id must be a UUID or None.")


def _validate_identifier(
    identifier: object,
    name: str,
) -> None:
    if not isinstance(identifier, (str, type(None))):
        raise TypeError(f"{name} must be a string or None.")
    if identifier is not None and identifier.strip() == "":
        raise ValueError(f"{name} must not be an empty string.")


def _validate_namespace(
    namespace: object,
) -> None:
    _validate_string(namespace, "namespace")


def _validate_string(
    value: object,
    name: str,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value.strip():
        raise ValueError(f"{name} must not be an empty string.")


def _validate_datetime(
    dt: object,
    name: str,
) -> None:
    if dt is None:
        return

    if not isinstance(dt, datetime):
        raise TypeError(f"{name} must be a datetime or None.")

    if dt.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")


def _validate_embedding(
    embedding: object,
) -> None:
    if not isinstance(embedding, list):
        raise TypeError("embedding must be a list.")
    if not embedding:
        raise ValueError("embedding must not be an empty list.")

    for index, value in enumerate(embedding):
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise TypeError(
                f"embedding[{index}] must be a float or int, excluding bool."
            )

        if not math.isfinite(value):
            raise ValueError(f"embedding[{index}] must not contain NaN or infinity.")
