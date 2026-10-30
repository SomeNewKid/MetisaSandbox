from __future__ import annotations

from datetime import date as Date
from typing import Annotated

import pytest
from pydantic import Field

from metisa_mcp_server._helper import (
    _create_input_schema,
    create_declared_resource,
    create_declared_tool,
    create_resource,
    create_tool,
    with_output_schema,
)


# Placeholder for return type
class Flight:
    pass


@with_output_schema({})
def search_flights(
    origin: Annotated[str, Field(description="Departure city")],
    destination: Annotated[str, Field(description="Arrival city")],
    date: Annotated[Date, Field(description="Travel date")],
) -> list[Flight]:
    """Search for available flights."""
    ...


@with_output_schema({})
def flight_policy() -> str:
    """Provide the flight policy."""
    return "The flight policy"


def tool_with_no_output_schema() -> str:
    """This tool does not declare its output schema."""
    ...


def test_create_resource_for_flight_policy_resource() -> None:
    resource = create_resource(flight_policy)
    assert resource.name == "flight_policy"
    assert resource.description == "Provide the flight policy."
    assert resource.uri == "metisa://flight_policy"
    assert resource.mime_type == "text/plain"


def test_create_declared_resource_if_flight_policy_is_in_metisa_json() -> None:
    metisa: dict[str, object] = {"resources": ["flight_policy"]}
    resource = create_declared_resource(metisa, flight_policy)
    assert resource is not None


def test_create_declared_resource_if_flight_policy_is_not_in_metisa_json() -> None:
    metisa: dict[str, object] = {"resources": ["other_policy"]}
    resource = create_declared_resource(metisa, flight_policy)
    assert resource is None


def test_tool_with_no_output_schema() -> None:
    with pytest.raises(ValueError):
        _ = create_tool(tool_with_no_output_schema)


def test_input_schema_for_search_flights_tool() -> None:
    input_schema = _create_input_schema(search_flights)
    expected_schema = {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Departure city",
            },
            "destination": {
                "type": "string",
                "description": "Arrival city",
            },
            "date": {
                "type": "string",
                "format": "date",
                "description": "Travel date",
            },
        },
        "required": ["origin", "destination", "date"],
        "additionalProperties": False,
    }

    assert input_schema == expected_schema


def test_create_tool_for_search_flights_tool() -> None:
    tool = create_tool(search_flights)
    assert tool.name == "search_flights"
    assert tool.description == "Search for available flights."

    expected_schema = {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Departure city",
            },
            "destination": {
                "type": "string",
                "description": "Arrival city",
            },
            "date": {
                "type": "string",
                "format": "date",
                "description": "Travel date",
            },
        },
        "required": ["origin", "destination", "date"],
        "additionalProperties": False,
    }

    assert tool.input_schema == expected_schema


def test_create_declared_tool_if_search_flights_tool_is_in_metisa_json() -> None:
    metisa: dict[str, object] = {"tools": ["search_flights"]}
    tool = create_declared_tool(metisa, search_flights)
    assert tool is not None


def test_create_declared_tool_if_search_flights_tool_is_not_in_metisa_json() -> None:
    metisa: dict[str, object] = {"tools": ["other_tool"]}
    tool = create_declared_tool(metisa, search_flights)
    assert tool is None
