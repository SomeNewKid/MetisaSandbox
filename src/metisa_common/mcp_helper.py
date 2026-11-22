"""Provide helper functions for the Metisa Sandbox and Harness."""

import inspect
from collections.abc import Callable
from typing import TypeVar, get_type_hints

from mcp.types import Tool
from pydantic import create_model

_ToolFunction = TypeVar("_ToolFunction", bound=Callable[..., object])


def create_tool(
    func: Callable[..., object],
) -> Tool:
    """Create an MCP tool definition for the function."""
    tool_name = func.__name__
    tool_description = func.__doc__
    tool_input_schema = _create_input_schema(func)
    tool_output_schema = getattr(func, "_metisa_output_schema", None)

    if not isinstance(tool_output_schema, dict):
        raise ValueError(f"Tool {tool_name} has not output schema.")

    return Tool(
        name=tool_name,
        description=tool_description,
        input_schema=tool_input_schema,
        output_schema=tool_output_schema,
    )


def with_output_schema(
    schema: dict[str, object],
) -> Callable[[_ToolFunction], _ToolFunction]:
    """Attach an output schema to a tool function."""

    def _decorate(func: _ToolFunction) -> _ToolFunction:
        # Attach metadata that is not declared on the callable's static type.
        setattr(func, "_metisa_output_schema", schema)  # noqa: B010
        return func

    return _decorate


def _create_input_schema(
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
