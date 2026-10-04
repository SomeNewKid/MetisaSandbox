"""Implememnt the MCP Server."""

from __future__ import annotations

from mcp import types
from mcp.server import Server, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route


async def _list_tools(
    _ctx: ServerRequestContext,
    _params: types.PaginatedRequestParams | None,
) -> types.ListToolsResult:
    schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    tool = types.Tool(
        name="say_hello", description="Return a greeting", input_schema=schema
    )
    return types.ListToolsResult(tools=[tool])


async def _call_tool(
    _ctx: ServerRequestContext,
    params: types.CallToolRequestParams,
) -> types.CallToolResult:
    available_tools = ["say_hello"]
    tool_name = params.name
    if tool_name not in available_tools:
        raise MCPError(-32602, f"Unknown tool: {tool_name}")
    tool_arguments = params.arguments
    if tool_arguments:
        raise MCPError(-32602, f"Tool accepts no arguments: {tool_name}")
    tool_result = _say_hello()
    content = types.TextContent(text=tool_result)
    return types.CallToolResult(content=[content])


async def _list_resources(
    _ctx: ServerRequestContext,
    _params: types.PaginatedRequestParams | None,
) -> types.ListResourcesResult:
    resource = types.Resource(
        name="hello",
        uri="metisa://hello",
        description="A greeting resource",
        mime_type="text/plain",
    )
    return types.ListResourcesResult(resources=[resource])


async def _read_resource(
    _ctx: ServerRequestContext,
    params: types.ReadResourceRequestParams,
) -> types.ReadResourceResult:
    if params.uri != "metisa://hello":
        raise MCPError(-32002, f"Resource not found: {params.uri}")
    greeting = _get_hello()
    content = types.TextResourceContents(
        uri=params.uri,
        mime_type="text/plain",
        text=greeting,
    )
    return types.ReadResourceResult(contents=[content])


async def _health(
    _request: Request,
) -> PlainTextResponse:
    return PlainTextResponse("OK", status_code=200)


def _say_hello() -> str:
    """Return a greeting."""
    return "Hello, World!"


def _get_hello() -> str:
    """Get the content of the greeting resource."""
    return "Hello, World!"


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
            "metisa-mcp-server:8000",
            "127.0.0.1:8000",
            "localhost:8000",
        ],
        allowed_origins=[]
    ),
    custom_starlette_routes=[
        Route("/health", endpoint=_health, methods=["GET"]),
    ],
)
