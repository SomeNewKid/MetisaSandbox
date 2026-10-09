from __future__ import annotations

from datetime import date as Date
from typing import Annotated

from pydantic import Field

from metisa_mcp_server.helper import (
    create_declared_resource,
    create_declared_tool,
    create_input_schema,
    create_resource,
    create_tool,
)


# Placeholder for return type
class Flight:
    pass


def search_flights(
    origin: Annotated[str, Field(description="Departure city")],
    destination: Annotated[str, Field(description="Arrival city")],
    date: Annotated[Date, Field(description="Travel date")],
) -> list[Flight]:
    """Search for available flights."""
    ...


def flight_policy() -> str:
    """Provide the flight policy."""
    return "The flight policy"


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


def test_input_schema_for_search_flights_tool() -> None:
    input_schema = create_input_schema(search_flights)
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
