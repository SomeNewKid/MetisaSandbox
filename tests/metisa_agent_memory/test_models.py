from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest

from metisa_agent_memory._models import (
    Episode,
    JsonObject,
    JsonValue,
    Memory,
    validate_json_object,
)

_ROW_ID = UUID("f32002c6-1723-4d21-8d74-c69e14c5d884")
_CREATED_AT = datetime(2026, 11, 4, 10, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 11, 4, 10, tzinfo=UTC)


@pytest.fixture(params=["episode", "memory"])
def memory_record(request: pytest.FixtureRequest) -> Episode | Memory:
    if request.param == "episode":
        return Episode(
            id=None,
            namespace="default",
            agent_id=None,
            run_id=None,
            trace_id=None,
            kind="observation",
            content={},
            metadata={},
            created_at=None,
            expires_at=None,
        )

    return Memory(
        id=None,
        namespace="default",
        subject="response_preferences",
        content={},
        text="The user prefers concise answers.",
        embedding=[0.25, -0.5, 0.75],
        metadata={},
        valid_to=None,
        created_at=None,
        updated_at=None,
        expires_at=None,
    )


@pytest.mark.parametrize(
    ("content", "metadata"),
    [
        pytest.param({}, {}, id="empty"),
        pytest.param(
            {"messages": [{"text": "Remember this.", "score": 0.5}]},
            {"tags": ["communication"], "reviewed": False, "source": None},
            id="nested",
        ),
    ],
)
def test_model_validate_accepts_valid_content_and_metadata(
    memory_record: Episode | Memory,
    content: JsonObject,
    metadata: JsonObject,
) -> None:
    memory_record.content = content
    memory_record.metadata = metadata

    assert memory_record.validate() is None
    assert memory_record.content == content
    assert memory_record.metadata == metadata


@pytest.mark.parametrize("field_name", ["content", "metadata"])
@pytest.mark.parametrize(
    ("invalid_value", "error_type"),
    [
        pytest.param([], TypeError, id="not-an-object"),
        pytest.param(
            {"nested": [{"tags": {"communication"}}]},
            TypeError,
            id="unsupported-nested-value",
        ),
        pytest.param({"nested": {1: "value"}}, TypeError, id="non-string-key"),
        pytest.param({"score": float("nan")}, ValueError, id="non-finite-float"),
    ],
)
def test_model_validate_rejects_invalid_content_or_metadata(
    memory_record: Episode | Memory,
    field_name: str,
    invalid_value: object,
    error_type: type[Exception],
) -> None:
    # Dataclasses allow mutation after construction, including invalid payloads.
    setattr(memory_record, field_name, invalid_value)

    with pytest.raises(error_type):
        memory_record.validate()


@pytest.mark.parametrize("value", [None, _ROW_ID])
def test_model_validate_accepts_optional_uuid(
    memory_record: Episode | Memory, value: UUID | None
) -> None:
    memory_record.id = value

    assert memory_record.validate() is None


@pytest.mark.parametrize("value", [str(_ROW_ID), "invalid", 42, True, b"uuid"])
def test_model_validate_rejects_non_uuid_id(
    memory_record: Episode | Memory, value: object
) -> None:
    # Intentionally bypass static typing to exercise runtime validation.
    memory_record.id = cast(UUID | None, value)

    with pytest.raises(TypeError):
        memory_record.validate()


@pytest.mark.parametrize(
    ("memory_record", "field_name"),
    [
        ("episode", "namespace"),
        ("episode", "kind"),
        ("memory", "namespace"),
        ("memory", "text"),
    ],
    indirect=["memory_record"],
)
@pytest.mark.parametrize(
    ("value", "error_type"),
    [
        (None, TypeError),
        (42, TypeError),
        (True, TypeError),
        ([], TypeError),
        ("", ValueError),
        (" \t\n", ValueError),
    ],
)
def test_model_validate_rejects_invalid_required_text(
    memory_record: Episode | Memory,
    field_name: str,
    value: object,
    error_type: type[Exception],
) -> None:
    setattr(memory_record, field_name, value)

    with pytest.raises(error_type):
        memory_record.validate()


@pytest.mark.parametrize("memory_record", ["episode"], indirect=True)
@pytest.mark.parametrize("field_name", ["agent_id", "run_id", "trace_id"])
@pytest.mark.parametrize("value", [None, "identifier-1", " identifier-1 "])
def test_episode_validate_accepts_optional_text(
    memory_record: Episode,
    field_name: str,
    value: str | None,
) -> None:
    setattr(memory_record, field_name, value)

    assert memory_record.validate() is None


@pytest.mark.parametrize("memory_record", ["episode"], indirect=True)
@pytest.mark.parametrize("field_name", ["agent_id", "run_id", "trace_id"])
@pytest.mark.parametrize("value", ["", " ", "\t\n", " \t\r\n "])
def test_episode_validate_rejects_blank_identifiers(
    memory_record: Episode,
    field_name: str,
    value: str,
) -> None:
    setattr(memory_record, field_name, value)

    with pytest.raises(ValueError):
        memory_record.validate()


@pytest.mark.parametrize("memory_record", ["episode"], indirect=True)
@pytest.mark.parametrize("field_name", ["agent_id", "run_id", "trace_id"])
@pytest.mark.parametrize("value", [42, False, [], _ROW_ID])
def test_episode_validate_rejects_non_string_optional_text(
    memory_record: Episode,
    field_name: str,
    value: object,
) -> None:
    setattr(memory_record, field_name, value)

    with pytest.raises(TypeError):
        memory_record.validate()


@pytest.mark.parametrize("memory_record", ["memory"], indirect=True)
@pytest.mark.parametrize("value", [None, 42, False, {}])
def test_memory_validate_rejects_non_string_subject(
    memory_record: Memory, value: object
) -> None:
    memory_record.subject = cast(str, value)

    with pytest.raises(TypeError):
        memory_record.validate()


@pytest.mark.parametrize(
    ("memory_record", "field_name"),
    [
        ("episode", "created_at"),
        ("episode", "expires_at"),
        ("memory", "created_at"),
        ("memory", "updated_at"),
        ("memory", "valid_to"),
        ("memory", "expires_at"),
    ],
    indirect=["memory_record"],
)
@pytest.mark.parametrize(
    "value",
    [
        None,
        _CREATED_AT,
        datetime(2020, 1, 1, tzinfo=timezone(timedelta(hours=8))),
    ],
    ids=["unset", "utc", "historical-non-utc"],
)
def test_model_validate_accepts_optional_aware_timestamps(
    memory_record: Episode | Memory,
    field_name: str,
    value: datetime | None,
) -> None:
    setattr(memory_record, field_name, value)

    assert memory_record.validate() is None


@pytest.mark.parametrize(
    ("memory_record", "field_name"),
    [
        ("episode", "created_at"),
        ("episode", "expires_at"),
        ("memory", "created_at"),
        ("memory", "updated_at"),
        ("memory", "valid_to"),
        ("memory", "expires_at"),
    ],
    indirect=["memory_record"],
)
@pytest.mark.parametrize(
    ("value", "error_type"),
    [
        pytest.param("2026-11-04T10:00:00Z", TypeError, id="string"),
        pytest.param(_CREATED_AT.date(), TypeError, id="date-only"),
        pytest.param(1793786400, TypeError, id="unix-timestamp"),
        pytest.param(datetime(2026, 11, 4), ValueError, id="naive-datetime"),
    ],
)
def test_model_validate_rejects_invalid_timestamps(
    memory_record: Episode | Memory,
    field_name: str,
    value: object,
    error_type: type[Exception],
) -> None:
    setattr(memory_record, field_name, value)

    with pytest.raises(error_type):
        memory_record.validate()


@pytest.mark.parametrize("memory_record", ["memory"], indirect=True)
@pytest.mark.parametrize("value", [[0.25, -0.5, 0.75], [0, -1, 2.5]])
def test_memory_validate_accepts_finite_numeric_embedding(
    memory_record: Memory, value: list[float]
) -> None:
    memory_record.embedding = value

    assert memory_record.validate() is None


@pytest.mark.parametrize("memory_record", ["memory"], indirect=True)
@pytest.mark.parametrize(
    ("value", "error_type"),
    [
        pytest.param(None, TypeError, id="unset"),
        pytest.param((0.25, 0.5), TypeError, id="tuple"),
        pytest.param("[0.25, 0.5]", TypeError, id="string"),
        pytest.param(["0.25"], TypeError, id="string-element"),
        pytest.param([None], TypeError, id="null-element"),
        pytest.param([True], TypeError, id="true-element"),
        pytest.param([False], TypeError, id="false-element"),
        pytest.param([[0.25]], TypeError, id="nested-list"),
        pytest.param([float("nan")], ValueError, id="nan"),
        pytest.param([float("inf")], ValueError, id="positive-infinity"),
        pytest.param([float("-inf")], ValueError, id="negative-infinity"),
    ],
)
def test_memory_validate_rejects_invalid_embedding(
    memory_record: Memory,
    value: object,
    error_type: type[Exception],
) -> None:
    memory_record.embedding = cast(list[float], value)

    with pytest.raises(error_type):
        memory_record.validate()


def test_episode_supports_creation_and_assigned_database_values() -> None:
    content: JsonObject = {"messages": [{"role": "user", "text": "Remember this."}]}
    metadata: JsonObject = {"tags": ["conversation"], "reviewed": False}
    episode = Episode(
        id=None,
        namespace="project:metisa",
        agent_id="sample_agent",
        run_id="run-1",
        trace_id="trace-1",
        kind="conversation",
        content=content,
        metadata=metadata,
        created_at=None,
        expires_at=_EXPIRES_AT,
    )

    assert episode.id is None
    assert episode.created_at is None
    assert episode.namespace == "project:metisa"
    assert episode.agent_id == "sample_agent"
    assert episode.run_id == "run-1"
    assert episode.trace_id == "trace-1"
    assert episode.kind == "conversation"
    assert episode.content == content
    assert episode.metadata == metadata
    assert episode.expires_at == _EXPIRES_AT

    stored_episode = replace(episode, id=_ROW_ID, created_at=_CREATED_AT)

    assert stored_episode.id == _ROW_ID
    assert stored_episode.created_at == _CREATED_AT
    assert stored_episode.content == content
    assert episode.id is None


def test_episode_supports_missing_optional_context() -> None:
    episode = Episode(
        id=None,
        namespace="default",
        agent_id=None,
        run_id=None,
        trace_id=None,
        kind="observation",
        content={},
        metadata={},
        created_at=None,
        expires_at=None,
    )

    assert episode.agent_id is None
    assert episode.run_id is None
    assert episode.trace_id is None
    assert episode.expires_at is None


def test_memory_supports_creation_and_assigned_database_values() -> None:
    content: JsonObject = {"preference": "response_length", "value": "concise"}
    metadata: JsonObject = {"tags": ["communication"]}
    memory = Memory(
        id=None,
        namespace="project:metisa",
        subject="response_preferences",
        content=content,
        text="The user prefers concise answers.",
        embedding=[0.25, -0.5, 0.75],
        metadata=metadata,
        valid_to=None,
        created_at=None,
        updated_at=None,
        expires_at=None,
    )

    assert memory.id is None
    assert memory.created_at is None
    assert memory.updated_at is None
    assert memory.namespace == "project:metisa"
    assert memory.subject == "response_preferences"
    assert memory.content == content
    assert memory.text == "The user prefers concise answers."
    assert memory.embedding == [0.25, -0.5, 0.75]
    assert memory.metadata == metadata
    assert memory.valid_to is None
    assert memory.expires_at is None

    stored_memory = replace(
        memory,
        id=_ROW_ID,
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
        valid_to=_EXPIRES_AT,
        expires_at=_EXPIRES_AT,
    )

    assert stored_memory.id == _ROW_ID
    assert stored_memory.created_at == _CREATED_AT
    assert stored_memory.updated_at == _CREATED_AT
    assert stored_memory.valid_to == _EXPIRES_AT
    assert stored_memory.expires_at == _EXPIRES_AT
    assert memory.id is None


@pytest.mark.parametrize(
    "value",
    [None, True, False, 0, -42, 1.25, "", "Hello, 世界", [], {}],
)
def test_validate_json_object_accepts_json_values_inside_objects(
    value: JsonValue,
) -> None:
    assert validate_json_object({"value": value}) is None


def test_validate_json_object_accepts_empty_object() -> None:
    assert validate_json_object({}) is None


def test_validate_json_object_preserves_nested_payload() -> None:
    payload: JsonObject = {
        "messages": [{"role": "user", "text": "Remember this."}],
        "metadata": {"tags": ["sales", "analysis"], "reviewed": False},
        "result": [None, 3, 0.5, {"success": True}],
    }
    expected: JsonObject = {
        "messages": [{"role": "user", "text": "Remember this."}],
        "metadata": {"tags": ["sales", "analysis"], "reviewed": False},
        "result": [None, 3, 0.5, {"success": True}],
    }

    validate_json_object(payload)

    assert payload == expected


@pytest.mark.parametrize("value", [None, True, 42, 1.5, "text", [], ()])
def test_validate_json_object_requires_top_level_dictionary(value: object) -> None:
    with pytest.raises(TypeError):
        validate_json_object(value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param({"tag"}, id="set"),
        pytest.param(frozenset({"tag"}), id="frozenset"),
        pytest.param(("tag",), id="tuple"),
        pytest.param(b"text", id="bytes"),
        pytest.param(bytearray(b"text"), id="bytearray"),
        pytest.param(_CREATED_AT, id="datetime"),
        pytest.param(_ROW_ID, id="uuid"),
        pytest.param(Decimal("0.5"), id="decimal"),
        pytest.param(1 + 2j, id="complex"),
        pytest.param(object(), id="object"),
    ],
)
def test_validate_json_object_rejects_unsupported_nested_values(value: object) -> None:
    with pytest.raises(TypeError):
        validate_json_object({"items": [{"value": value}]})


@pytest.mark.parametrize("key", [1, False, None, ("key",)])
def test_validate_json_object_rejects_non_string_keys(key: object) -> None:
    with pytest.raises(TypeError):
        validate_json_object({"nested": [{key: "value"}]})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_validate_json_object_rejects_non_finite_floats(value: float) -> None:
    with pytest.raises(ValueError):
        validate_json_object({"items": [{"score": value}]})


def test_validate_json_object_rejects_dictionary_cycle() -> None:
    payload: dict[str, object] = {}
    payload["self"] = payload

    with pytest.raises(ValueError):
        validate_json_object(payload)


def test_validate_json_object_rejects_list_cycle() -> None:
    items: list[object] = []
    items.append(items)

    with pytest.raises(ValueError):
        validate_json_object({"items": items})


def test_validate_json_object_rejects_mixed_container_cycle() -> None:
    payload: dict[str, object] = {}
    payload["items"] = [payload]

    with pytest.raises(ValueError):
        validate_json_object(payload)


def test_validate_json_object_accepts_shared_containers_without_cycles() -> None:
    shared_object: JsonObject = {"source": "conversation"}
    shared_list: list[JsonValue] = ["communication"]
    payload: JsonObject = {
        "first": shared_object,
        "second": shared_object,
        "tags": [shared_list, shared_list],
    }

    assert validate_json_object(payload) is None


def test_validate_json_object_reports_default_root_name() -> None:
    with pytest.raises(TypeError, match="value"):
        validate_json_object([])


def test_validate_json_object_reports_named_nested_location() -> None:
    with pytest.raises(TypeError) as error:
        validate_json_object({"items": [{"score": object()}]}, name="content")

    message = str(error.value)
    assert "content" in message
    assert "items" in message
    assert "[0]" in message
    assert "score" in message
