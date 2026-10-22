"""Provide helper functions for the Metisa MCP Server."""

import inspect
from collections.abc import Callable
from typing import get_type_hints

from mcp.types import Resource, Tool
from pydantic import create_model

# This helper would be unnecessary if we used the built-in MCPServer.
# However, we're using the lower-level Server because this is a learning project.


def create_declared_resource(
    metisa: dict[str, object],
    func: Callable[..., object],
) -> Resource | None:
    """Create an MCP resource definition if metisa.toml declares the resource."""
    declared_resources = _create_string_list(metisa, "resources")

    if not declared_resources:
        return None

    resource_name = func.__name__

    if resource_name not in declared_resources:
        return None

    return create_resource(func)


def create_resource(
    func: Callable[..., object],
) -> Resource:
    """Create an MCP resource definition for the function."""
    resource_name = func.__name__
    resource_description = func.__doc__

    return Resource(
        name=resource_name,
        description=resource_description,
        uri=f"metisa://{resource_name}",
        mime_type="text/plain",
    )


def create_declared_tool(
    metisa: dict[str, object],
    func: Callable[..., object],
) -> Tool | None:
    """Create an MCP tool definition if metisa.toml declares the tool."""
    declared_tools = _create_string_list(metisa, "tools")

    if not declared_tools:
        return None

    tool_name = func.__name__

    if tool_name not in declared_tools:
        return None

    return create_tool(func)


def create_tool(
    func: Callable[..., object],
) -> Tool:
    """Create an MCP tool definition for the function."""
    tool_name = func.__name__
    tool_description = func.__doc__

    return Tool(
        name=tool_name,
        description=tool_description,
        input_schema=create_input_schema(func),
    )


def create_input_schema(
    func: Callable[..., object],
) -> dict[str, object]:
    """Create an input schema for the given function."""
    # Retrieve runtime type hints (including Annotated metadata)
    type_hints = get_type_hints(func, include_extras=True)

    # Inspect the signature to handle field names and default values
    signature = inspect.signature(func)

    fields = {}
    for name, param in signature.parameters.items():
        # fall back to object if no type hint is provided
        hint = type_hints.get(name, object)

        # Pydantic's create_model expects Ellipsis (...) if a field is required
        default = param.default if param.default is not inspect.Parameter.empty else ...

        fields[name] = (hint, default)

    # Dynamically create the Pydantic model
    model = create_model(func.__name__, **fields)

    # Generate and clean up the schema format
    schema = model.model_json_schema()
    schema.pop("title", None)
    for property in schema.get("properties", {}).values():
        property.pop("title", None)
    schema["additionalProperties"] = False
    return schema


def _create_string_list(
    metisa: dict[str, object],
    field_name: str,
) -> list[str]:
    raw_items = metisa.get(field_name)
    if not raw_items:
        return []

    if not isinstance(raw_items, list):
        return []

    collection: list[str] = []
    for raw_item in raw_items:
        if isinstance(raw_item, str):
            if raw_item:
                collection.append(raw_item)

    return collection
