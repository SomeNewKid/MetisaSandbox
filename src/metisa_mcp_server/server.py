"""Implememnt the MCP Server."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from jsonschema import ValidationError, validate
from mcp import types
from mcp.server import Server, ServerRequestContext
from mcp.server.context import CallNext, HandlerResult
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from opentelemetry.context import Context, attach, detach
from opentelemetry.propagate import extract
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from ._authentication import (
    RunTokenMiddleware,
)
from ._helper import (
    create_declared_resource,
    create_declared_tool,
    create_resource,
    create_tool,
)
from ._resources import (
    test_resource_1,
    test_resource_2,
    test_resource_3,
)
from ._telemetry import initialize_tracing
from ._tools._anonymize_entities_in_text_tool import (
    anonymize_entities_in_text,
)
from ._tools._convert_document_to_markdown_tool import (
    convert_document_to_markdown,
)
from ._tools._execute_starlark_code_tools import (
    execute_starlark_code,
)
from ._tools._get_active_items_from_database_tool import (
    get_active_items_from_database,
)
from ._tools._get_classification_indicators_tool import (
    get_classification_indicators,
)
from ._tools._get_matching_chunks_from_document_tool import (
    get_matching_chunks_from_document,
)
from ._tools._get_moderation_labels_tool import (
    get_moderation_labels,
)
from ._tools._get_title_from_url_tool import (
    get_title_from_url,
)
from ._tools._read_content_from_url_tool import (
    read_content_from_url,
)
from ._tools._retrieve_content_from_document_tool import (
    retrieve_content_from_document,
)
from ._tools._screen_user_input_tool import (
    screen_user_input,
)
from ._tools._test_greeting_1_tool import (
    test_greeting_1,
)
from ._tools._test_greeting_2_tool import (
    test_greeting_2,
)
from ._tools._test_greeting_3_tool import (
    test_greeting_3,
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
        screen_user_input,
        test_greeting_1,
    ],
    metisa_json,
    [
        anonymize_entities_in_text,
        convert_document_to_markdown,
        execute_starlark_code,
        get_active_items_from_database,
        get_classification_indicators,
        get_matching_chunks_from_document,
        get_moderation_labels,
        get_title_from_url,
        read_content_from_url,
        retrieve_content_from_document,
        test_greeting_2,
        test_greeting_3,
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
    ctx: ServerRequestContext,
    _params: types.PaginatedRequestParams | None,
) -> types.ListToolsResult:
    request = ctx.request
    if not isinstance(request, Request):
        raise RuntimeError("HTTP request context is required.")
    user_sid = request.state.user_sid
    if not user_sid:
        raise RuntimeError("Tool list requires user SID.")

    definitions: list[types.Tool] = []
    for tool in TOOL_REGISTRY:
        definitions.append(tool.definition)
    return types.ListToolsResult(tools=definitions)


async def _call_tool(
    ctx: ServerRequestContext,
    params: types.CallToolRequestParams,
) -> types.CallToolResult:
    request = ctx.request
    if not isinstance(request, Request):
        raise RuntimeError("HTTP request context is required.")
    user_sid = request.state.user_sid
    if not user_sid:
        raise RuntimeError("Tool call requires user SID.")

    tool_name = params.name
    requested_tool = None
    for tool in TOOL_REGISTRY:
        if tool.definition.name == tool_name:
            requested_tool = tool
            break
    if not requested_tool:
        raise MCPError(-32602, f"Unknown tool: {tool_name}")

    tool_arguments = params.arguments or {}

    tool_input_schema = requested_tool.definition.input_schema
    if not tool_input_schema:
        raise MCPError(-32602, f"Tool has no input schema: {tool_name}")
    try:
        validate(
            instance=tool_arguments,
            schema=tool_input_schema,
        )
    except ValidationError as error:
        raise MCPError(-32602, error.message) from error

    try:
        tool_result = requested_tool.function(**tool_arguments)
    except RuntimeError as error:
        content = types.TextContent(text=str(error))
        return types.CallToolResult(
            content=[content],
            is_error=True,
        )

    tool_output_schema = requested_tool.definition.output_schema
    if not tool_output_schema:
        raise MCPError(-32602, f"Tool has no output schema: {tool_name}")
    try:
        validate(
            instance=tool_result,
            schema=tool_output_schema,
        )
    except ValidationError as error:
        raise MCPError(-32602, error.message) from error

    if not isinstance(tool_result, dict):
        raise MCPError(-32602, f"Tool returned a non-JSON result: {tool_name}")

    serialized_result = json.dumps(tool_result, allow_nan=False)
    text_content = types.TextContent(text=serialized_result)

    return types.CallToolResult(
        content=[text_content],
        structured_content=tool_result,
    )


async def _list_resources(
    ctx: ServerRequestContext,
    _params: types.PaginatedRequestParams | None,
) -> types.ListResourcesResult:
    request = ctx.request
    if not isinstance(request, Request):
        raise RuntimeError("HTTP request context is required.")
    user_sid = request.state.user_sid
    if not user_sid:
        raise RuntimeError("Resource list requires user SID.")

    definitions: list[types.Resource] = []
    for resource in RESOURCE_REGISTRY:
        definitions.append(resource.definition)
    return types.ListResourcesResult(resources=definitions)


async def _read_resource(
    ctx: ServerRequestContext,
    params: types.ReadResourceRequestParams,
) -> types.ReadResourceResult:
    request = ctx.request
    if not isinstance(request, Request):
        raise RuntimeError("HTTP request context is required.")
    user_sid = request.state.user_sid
    if not user_sid:
        raise RuntimeError("Resource read requires user SID.")

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


@asynccontextmanager
async def _server_lifespan(
    _server: Server,
) -> AsyncGenerator[dict[str, object]]:
    provider = initialize_tracing()

    try:
        yield {}
    finally:
        provider.shutdown()


async def _http_trace_context(
    ctx: ServerRequestContext,
    call_next: CallNext,
) -> HandlerResult:
    request = ctx.request

    if not isinstance(request, Request):
        return await call_next(ctx)

    # Reconstructs the remote parent from the HTTP headers
    parent_content = extract(
        carrier=request.headers,
        context=Context(),
    )
    token = attach(parent_content)  # make the remote parent current

    try:
        return await call_next(ctx)
    finally:
        detach(token)


server = Server(
    "Metisa MCP Server",
    lifespan=_server_lifespan,
    on_list_tools=_list_tools,
    on_call_tool=_call_tool,
    on_list_resources=_list_resources,
    on_read_resource=_read_resource,
)

server.middleware.insert(0, _http_trace_context)

_mcp_http_app = server.streamable_http_app(
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

app = RunTokenMiddleware(
    _mcp_http_app,
    public_key_path=Path("/sandbox-source/metisa-public-key.pem"),
    run_identifier=os.environ["METISA_RUN_ID"],
)
