"""Probes related to the private-network MCP server sidecar."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import traceback
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from metisa_common.specification_models import Capability

from ..probe_models import ProbeContext, ProbeGroup, ProbeResult

if TYPE_CHECKING:
    from mcp import Client

_MCP_SERVER_ALIAS = "metisa-mcp-server"
_MCP_SERVER_URL = f"http://{_MCP_SERVER_ALIAS}:8000/mcp"
_HELLO_RESOURCE_URI = "metisa://hello"
_EXPECTED_GREETING = "Hello, World!"
_TIMEOUT_SECONDS = 5


def mcp_server_alias_resolves(probe_context: ProbeContext) -> ProbeResult:
    """Verify the MCP sidecar alias resolves to non-loopback addresses."""
    probe_name = "container__mcp__mcp_server_alias_resolves"
    if Capability.MCP_CLIENT not in probe_context.specification.capabilities:
        return ProbeResult.success(
            probe_name, "MCP client is disabled. Skipping probe."
        )
    try:
        addresses = asyncio.run(_resolve_alias())
    except Exception as error:
        return ProbeResult.failure(probe_name, f"MCP alias resolution failed: {error}")
    if not addresses or any(
        ipaddress.ip_address(value).is_loopback for value in addresses
    ):
        return ProbeResult.failure(
            probe_name, "MCP alias has no valid sidecar addresses."
        )
    return ProbeResult.success(
        probe_name, "MCP alias resolves to non-loopback addresses."
    )


def say_hello_tool_is_available(probe_context: ProbeContext) -> ProbeResult:
    """Verify MCP tool discovery includes say_hello."""
    return _run_mcp_probe(probe_context, "say_hello_tool_is_available", _list_tools)


def say_hello_tool_returns_expected_greeting(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify say_hello succeeds and returns the expected greeting."""
    return _run_mcp_probe(
        probe_context, "say_hello_tool_returns_expected_greeting", _call_tool
    )


def hello_resource_is_available(probe_context: ProbeContext) -> ProbeResult:
    """Verify MCP resource discovery includes the hello resource."""
    return _run_mcp_probe(probe_context, "hello_resource_is_available", _list_resources)


def hello_resource_returns_expected_greeting(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the hello resource returns the expected text and MIME type."""
    return _run_mcp_probe(
        probe_context, "hello_resource_returns_expected_greeting", _read_resource
    )


def _run_mcp_probe(
    probe_context: ProbeContext,
    name: str,
    operation: Callable[[Client], Awaitable[str | None]],
) -> ProbeResult:
    probe_name = f"container__mcp__{name}"
    if Capability.MCP_CLIENT not in probe_context.specification.capabilities:
        return ProbeResult.success(
            probe_name, "MCP client is disabled. Skipping probe."
        )
    try:
        failure = asyncio.run(_execute_operation(operation))
    except Exception as error:
        traceback_lines = traceback.format_exception(error)
        details = "".join(traceback_lines)
        message = f"MCP operation failed: {details}"
        return ProbeResult.failure(probe_name, message)
    if failure is not None:
        return ProbeResult.failure(probe_name, failure)
    return ProbeResult.success(probe_name, "MCP server returned the expected result.")


async def _execute_operation(
    operation: Callable[[Client], Awaitable[str | None]],
) -> str | None:
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    async with asyncio.timeout(_TIMEOUT_SECONDS):
        # Private-network calls must bypass the workload's internet proxy settings.
        async with httpx2.AsyncClient(
            trust_env=False, timeout=_TIMEOUT_SECONDS
        ) as http_client:
            transport = streamable_http_client(_MCP_SERVER_URL, http_client=http_client)
            async with Client(
                transport, read_timeout_seconds=_TIMEOUT_SECONDS
            ) as client:
                return await operation(client)


async def _resolve_alias() -> set[str]:
    async with asyncio.timeout(_TIMEOUT_SECONDS):
        loop = asyncio.get_running_loop()
        addresses = await loop.getaddrinfo(
            _MCP_SERVER_ALIAS, 8000, type=socket.SOCK_STREAM
        )
    return {str(address[4][0]) for address in addresses}


async def _list_tools(client: Client) -> str | None:
    result = await client.list_tools()
    if not any(tool.name == "say_hello" for tool in result.tools):
        return "MCP server did not advertise say_hello."
    return None


async def _call_tool(client: Client) -> str | None:
    from mcp import types

    result = await client.call_tool("say_hello", {})
    if result.is_error:
        return "say_hello returned a tool execution error."
    if len(result.content) != 1:
        return "say_hello did not return exactly one content block."
    content = result.content[0]
    if not isinstance(content, types.TextContent) or content.text != _EXPECTED_GREETING:
        return "say_hello did not return the expected text greeting."
    return None


async def _list_resources(client: Client) -> str | None:
    result = await client.list_resources()
    if not any(
        resource.name == "hello" and resource.uri == _HELLO_RESOURCE_URI
        for resource in result.resources
    ):
        return "MCP server did not advertise hello at metisa://hello."
    return None


async def _read_resource(client: Client) -> str | None:
    from mcp import types

    result = await client.read_resource(_HELLO_RESOURCE_URI)
    if len(result.contents) != 1:
        return "hello did not return exactly one resource content block."
    content = result.contents[0]
    if (
        not isinstance(content, types.TextResourceContents)
        or content.uri != _HELLO_RESOURCE_URI
        or content.mime_type != "text/plain"
        or content.text != _EXPECTED_GREETING
    ):
        return "hello returned an unexpected URI, MIME type, or text greeting."
    return None


MCP_PROBES = ProbeGroup(
    name="mcp",
    probes=(
        mcp_server_alias_resolves,
        say_hello_tool_is_available,
        say_hello_tool_returns_expected_greeting,
        hello_resource_is_available,
        hello_resource_returns_expected_greeting,
    ),
)
