"""Implememnt the MCP Server."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from jsonschema import ValidationError, validate
from mcp import types
from mcp.server import Server, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from .helper import (
    create_declared_resource,
    create_declared_tool,
    create_resource,
    create_tool,
)
from .resources import (
    test_resource_1,
    test_resource_2,
    test_resource_3,
)
from .tools import (
    get_active_items,
    test_tool_1,
    test_tool_2,
    test_tool_3,
)

_MCP_SERVER_PORT = 8000


root_directory = Path(__file__).parent
metisa_json_file = root_directory.with_name("metisa.json")

if not metisa_json_file.exists():
    raise RuntimeError("Metisa JSON file not found.")

with metisa_json_file.open("r", encoding="utf-8") as file:
    metisa_json = json.load(file)

if not isinstance(metisa_json, dict):
    raise RuntimeError("Invalid Metisa JSON file.")


@dataclass
class _RegisteredTool:
    definition: types.Tool
    function: Callable[..., object]


@dataclass
class _RegisteredResource:
    definition: types.Resource
    function: Callable[..., object]


def _create_tool_registry(
    required_tools: list[Callable],
    metisa: dict[str, object],
    optional_tools: list[Callable],
) -> list[_RegisteredTool]:
    registered_tools: list[_RegisteredTool] = []
    if required_tools:
        for required_tool in required_tools:
            definition = create_tool(required_tool)
            registered_tool = _RegisteredTool(definition, required_tool)
            registered_tools.append(registered_tool)
    if optional_tools:
        for optional_tool in optional_tools:
            definition = create_declared_tool(metisa, optional_tool)
            if definition:
                registered_tool = _RegisteredTool(definition, optional_tool)
                registered_tools.append(registered_tool)
    return registered_tools


def _create_resource_registry(
    required_resources: list[Callable],
    metisa: dict[str, object],
    optional_resources: list[Callable],
) -> list[_RegisteredResource]:
    registered_resources: list[_RegisteredResource] = []
    if required_resources:
        for required_resource in required_resources:
            definition = create_resource(required_resource)
            registered_resource = _RegisteredResource(definition, required_resource)
            registered_resources.append(registered_resource)
    if optional_resources:
        for optional_resource in optional_resources:
            definition = create_declared_resource(metisa, optional_resource)
            if definition:
                registered_resource = _RegisteredResource(definition, optional_resource)
                registered_resources.append(registered_resource)
    return registered_resources


TOOL_REGISTRY = _create_tool_registry(
    [
        test_tool_1,
    ],
    metisa_json,
    [
        test_tool_2,
        test_tool_3,
        get_active_items,
    ],
)

RESOURCE_REGISTRY = _create_resource_registry(
    [
        test_resource_1,
    ],
    metisa_json,
    [
        test_resource_2,
        test_resource_3,
    ],
)


async def _list_tools(
    _ctx: ServerRequestContext,
    _params: types.PaginatedRequestParams | None,
) -> types.ListToolsResult:
    definitions: list[types.Tool] = []
    for tool in TOOL_REGISTRY:
        definitions.append(tool.definition)
    return types.ListToolsResult(tools=definitions)


async def _call_tool(
    _ctx: ServerRequestContext,
    params: types.CallToolRequestParams,
) -> types.CallToolResult:
    tool_name = params.name

    requsted_tool = None
    for tool in TOOL_REGISTRY:
        if tool.definition.name == tool_name:
            requsted_tool = tool
            break
    if not requsted_tool:
        raise MCPError(-32602, f"Unknown tool: {tool_name}")

    tool_arguments = params.arguments or {}

    try:
        validate(
            instance=tool_arguments,
            schema=requsted_tool.definition.input_schema
        )
    except ValidationError as error:
        raise MCPError(-32602, error.message) from error

    tool_result = requsted_tool.function(**tool_arguments)
    if not isinstance(tool_result, str):
        raise MCPError(-32602, f"Tool returned a non-string result: {tool_name}")

    content = types.TextContent(text=tool_result)
    return types.CallToolResult(content=[content])


async def _list_resources(
    _ctx: ServerRequestContext,
    _params: types.PaginatedRequestParams | None,
) -> types.ListResourcesResult:
    definitions: list[types.Resource] = []
    for resource in RESOURCE_REGISTRY:
        definitions.append(resource.definition)
    return types.ListResourcesResult(resources=definitions)


async def _read_resource(
    _ctx: ServerRequestContext,
    params: types.ReadResourceRequestParams,
) -> types.ReadResourceResult:
    requested_uri = params.uri

    requested_resource = None
    for resource in RESOURCE_REGISTRY:
        if resource.definition.uri == requested_uri:
            requested_resource = resource
            break

    if not requested_resource:
        raise MCPError(-32002, f"Resource not found: {params.uri}")

    resource_contents = requested_resource.function()

    if requested_resource.definition.mime_type == "text/plain":
        if not isinstance(resource_contents, str):
            raise MCPError(-32002, f"Resource returned unexpected type: {params.uri}")
    else:
        raise MCPError(-32002, f"Resource returned unsupported type: {params.uri}")

    content = types.TextResourceContents(
        uri=params.uri,
        mime_type="text/plain",
        text=resource_contents,
    )
    return types.ReadResourceResult(contents=[content])


async def _health(
    _request: Request,
) -> PlainTextResponse:
    return PlainTextResponse("OK", status_code=200)


server = Server(
    "Metisa MCP Server",
    on_list_tools=_list_tools,
    on_call_tool=_call_tool,
    on_list_resources=_list_resources,
    on_read_resource=_read_resource,
)


app = server.streamable_http_app(
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            f"metisa-mcp-server:{_MCP_SERVER_PORT}",
            f"127.0.0.1:{_MCP_SERVER_PORT}",
            f"localhost:{_MCP_SERVER_PORT}",
        ],
        allowed_origins=[],
    ),
    custom_starlette_routes=[
        Route("/health", endpoint=_health, methods=["GET"]),
    ],
)
