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
_MCP_SERVER_PORT = 8000
_MCP_SERVER_URL = f"http://{_MCP_SERVER_ALIAS}:{_MCP_SERVER_PORT}/mcp"
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


def test_tool_1_is_available(probe_context: ProbeContext) -> ProbeResult:
    """Verify MCP tool discovery includes test_tool_1."""
    tool_name = "test_tool_1"

    async def _operation(client: Client) -> str | None:
        result = await client.list_tools()
        if not any(tool.name == tool_name for tool in result.tools):
            return f"MCP server did not advertise {tool_name}."
        return None

    return _run_mcp_probe(probe_context, "test_tool_1_is_available", _operation)


def test_tool_1_returns_expected_greeting(probe_context: ProbeContext) -> ProbeResult:
    """Verify test_tool_1 succeeds and returns the expected greeting."""
    tool_name = "test_tool_1"
    expected_greeting = "Hello, from test_tool_1."

    async def _operation(client: Client) -> str | None:
        from mcp import types

        result = await client.call_tool(tool_name, {})
        if result.is_error:
            return f"{tool_name} returned a tool execution error."
        if len(result.content) != 1:
            return f"{tool_name} did not return exactly one content block."
        content = result.content[0]
        if (
            not isinstance(content, types.TextContent)
            or content.text != expected_greeting
        ):
            return f"{tool_name} did not return the expected text greeting."
        return None

    return _run_mcp_probe(
        probe_context, "test_tool_1_returns_expected_greeting", _operation
    )


def test_tool_2_returns_expected_greetings(probe_context: ProbeContext) -> ProbeResult:
    """Verify test_tool_2 is usable only when declared and handles both names."""
    tool_name = "test_tool_2"
    mcp_server = probe_context.specification.mcp_server
    declared = mcp_server is not None and tool_name in mcp_server.tools

    async def _operation(client: Client) -> str | None:
        from mcp import types
        from mcp.shared.exceptions import MCPError

        result = await client.list_tools()
        listed = any(tool.name == tool_name for tool in result.tools)
        if not declared:
            if listed:
                return f"MCP server advertised undeclared tool {tool_name}."
            try:
                await client.call_tool(tool_name, {"name": "Susan"})
            except MCPError as error:
                if (
                    error.code == -32602
                    and error.message == f"Unknown tool: {tool_name}"
                ):
                    return None
                raise
            return f"MCP server allowed a call to undeclared tool {tool_name}."

        if not listed:
            return f"MCP server did not advertise {tool_name}."
        for name, expected_greeting in (
            ("", "Hello, from test_tool_2."),
            ("Susan", "Hello, Susan, from test_tool_2."),
        ):
            response = await client.call_tool(tool_name, {"name": name})
            if response.is_error:
                return f"{tool_name} returned a tool execution error for name {name!r}."
            if len(response.content) != 1:
                return (
                    f"{tool_name} did not return exactly one content block "
                    f"for name {name!r}."
                )
            content = response.content[0]
            if (
                not isinstance(content, types.TextContent)
                or content.text != expected_greeting
            ):
                return (
                    f"{tool_name} did not return the expected text greeting "
                    f"for name {name!r}."
                )
        return None

    return _run_mcp_probe(
        probe_context, "test_tool_2_returns_expected_greetings", _operation
    )


def test_tool_3_validates_name(probe_context: ProbeContext) -> ProbeResult:
    """Verify test_tool_3 is usable only when declared and validates names."""
    tool_name = "test_tool_3"
    expected_greeting = "Hello, Susan, from test_tool_3."
    mcp_server = probe_context.specification.mcp_server
    declared = mcp_server is not None and tool_name in mcp_server.tools

    async def _operation(client: Client) -> str | None:
        from mcp import types
        from mcp.shared.exceptions import MCPError

        result = await client.list_tools()
        listed = any(tool.name == tool_name for tool in result.tools)
        if not declared:
            if listed:
                return f"MCP server advertised undeclared tool {tool_name}."
            try:
                await client.call_tool(tool_name, {"name": "Susan"})
            except MCPError as error:
                if (
                    error.code == -32602
                    and error.message == f"Unknown tool: {tool_name}"
                ):
                    return None
                raise
            return f"MCP server allowed a call to undeclared tool {tool_name}."

        if not listed:
            return f"MCP server did not advertise {tool_name}."
        try:
            response = await client.call_tool(tool_name, {"name": ""})
        except MCPError:
            # The low-level server can report a tool exception as a protocol error.
            pass
        else:
            if not response.is_error:
                return f"{tool_name} did not reject an empty name."
        response = await client.call_tool(tool_name, {"name": "Susan"})
        if response.is_error:
            return f"{tool_name} returned a tool execution error for name 'Susan'."
        if len(response.content) != 1:
            return (
                f"{tool_name} did not return exactly one content block "
                "for name 'Susan'."
            )
        content = response.content[0]
        if (
            not isinstance(content, types.TextContent)
            or content.text != expected_greeting
        ):
            return (
                f"{tool_name} did not return the expected text greeting "
                "for name 'Susan'."
            )
        return None

    return _run_mcp_probe(probe_context, "test_tool_3_validates_name", _operation)


def test_tool_2_rejects_non_string_name(probe_context: ProbeContext) -> ProbeResult:
    """Verify declared test_tool_2 rejects a non-string name."""
    tool_name = "test_tool_2"
    probe_name = "test_tool_2_rejects_non_string_name"
    mcp_server = probe_context.specification.mcp_server
    if mcp_server is None or tool_name not in mcp_server.tools:
        return ProbeResult.success(
            f"container__mcp__{probe_name}",
            f"{tool_name} is not declared. Skipping probe.",
        )

    async def _operation(client: Client) -> str | None:
        from mcp.shared.exceptions import MCPError

        result = await client.list_tools()
        if not any(tool.name == tool_name for tool in result.tools):
            return f"MCP server did not advertise declared tool {tool_name}."
        try:
            response = await client.call_tool(tool_name, {"name": 42})
        except MCPError as error:
            if error.message == f"Unknown tool: {tool_name}":
                raise
            return None
        if not response.is_error:
            return f"{tool_name} did not reject a non-string name."
        return None

    return _run_mcp_probe(probe_context, probe_name, _operation)


def test_tool_2_rejects_additional_arguments(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify declared test_tool_2 rejects arguments beyond name."""
    tool_name = "test_tool_2"
    probe_name = "test_tool_2_rejects_additional_arguments"
    mcp_server = probe_context.specification.mcp_server
    if mcp_server is None or tool_name not in mcp_server.tools:
        return ProbeResult.success(
            f"container__mcp__{probe_name}",
            f"{tool_name} is not declared. Skipping probe.",
        )

    async def _operation(client: Client) -> str | None:
        from mcp.shared.exceptions import MCPError

        result = await client.list_tools()
        if not any(tool.name == tool_name for tool in result.tools):
            return f"MCP server did not advertise declared tool {tool_name}."
        try:
            response = await client.call_tool(
                tool_name, {"name": "Susan", "unexpected": "extra"}
            )
        except MCPError as error:
            if error.message == f"Unknown tool: {tool_name}":
                raise
            return None
        if not response.is_error:
            return f"{tool_name} did not reject an additional argument."
        return None

    return _run_mcp_probe(probe_context, probe_name, _operation)


def test_tool_3_rejects_non_string_name(probe_context: ProbeContext) -> ProbeResult:
    """Verify declared test_tool_3 rejects a non-string name."""
    tool_name = "test_tool_3"
    probe_name = "test_tool_3_rejects_non_string_name"
    mcp_server = probe_context.specification.mcp_server
    if mcp_server is None or tool_name not in mcp_server.tools:
        return ProbeResult.success(
            f"container__mcp__{probe_name}",
            f"{tool_name} is not declared. Skipping probe.",
        )

    async def _operation(client: Client) -> str | None:
        from mcp.shared.exceptions import MCPError

        result = await client.list_tools()
        if not any(tool.name == tool_name for tool in result.tools):
            return f"MCP server did not advertise declared tool {tool_name}."
        try:
            response = await client.call_tool(tool_name, {"name": 42})
        except MCPError as error:
            if error.message == f"Unknown tool: {tool_name}":
                raise
            return None
        if not response.is_error:
            return f"{tool_name} did not reject a non-string name."
        return None

    return _run_mcp_probe(probe_context, probe_name, _operation)


def test_tool_3_rejects_additional_arguments(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify declared test_tool_3 rejects arguments beyond name."""
    tool_name = "test_tool_3"
    probe_name = "test_tool_3_rejects_additional_arguments"
    mcp_server = probe_context.specification.mcp_server
    if mcp_server is None or tool_name not in mcp_server.tools:
        return ProbeResult.success(
            f"container__mcp__{probe_name}",
            f"{tool_name} is not declared. Skipping probe.",
        )

    async def _operation(client: Client) -> str | None:
        from mcp.shared.exceptions import MCPError

        result = await client.list_tools()
        if not any(tool.name == tool_name for tool in result.tools):
            return f"MCP server did not advertise declared tool {tool_name}."
        try:
            response = await client.call_tool(
                tool_name, {"name": "Susan", "unexpected": "extra"}
            )
        except MCPError as error:
            if error.message == f"Unknown tool: {tool_name}":
                raise
            return None
        if not response.is_error:
            return f"{tool_name} did not reject an additional argument."
        return None

    return _run_mcp_probe(probe_context, probe_name, _operation)


def test_resource_1_is_available(probe_context: ProbeContext) -> ProbeResult:
    """Verify MCP resource discovery includes test_resource_1."""
    resource_name = "test_resource_1"
    resource_uri = "metisa://test_resource_1"

    async def _operation(client: Client) -> str | None:
        result = await client.list_resources()
        if not any(
            resource.name == resource_name and resource.uri == resource_uri
            for resource in result.resources
        ):
            return f"MCP server did not advertise {resource_name} at {resource_uri}."
        return None

    return _run_mcp_probe(probe_context, "test_resource_1_is_available", _operation)


def test_resource_1_returns_expected_greeting(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify test_resource_1 returns the expected text and MIME type."""
    resource_name = "test_resource_1"
    resource_uri = "metisa://test_resource_1"
    expected_greeting = "Hello, from test_resource_1."

    async def _operation(client: Client) -> str | None:
        from mcp import types

        result = await client.read_resource(resource_uri)
        if len(result.contents) != 1:
            return f"{resource_name} did not return exactly one resource content block."
        content = result.contents[0]
        if (
            not isinstance(content, types.TextResourceContents)
            or content.uri != resource_uri
            or content.mime_type != "text/plain"
            or content.text != expected_greeting
        ):
            return (
                f"{resource_name} returned an unexpected URI, MIME type, "
                "or text greeting."
            )
        return None

    return _run_mcp_probe(
        probe_context, "test_resource_1_returns_expected_greeting", _operation
    )


def test_resource_2_matches_declaration(probe_context: ProbeContext) -> ProbeResult:
    """Verify test_resource_2 is listed and readable only when declared."""
    resource_name = "test_resource_2"
    resource_uri = "metisa://test_resource_2"
    expected_greeting = "Hello, from test_resource_2."
    mcp_server = probe_context.specification.mcp_server
    declared = mcp_server is not None and resource_name in mcp_server.resources

    async def _operation(client: Client) -> str | None:
        from mcp import types
        from mcp.shared.exceptions import MCPError

        result = await client.list_resources()
        if declared:
            if not any(
                resource.name == resource_name and resource.uri == resource_uri
                for resource in result.resources
            ):
                return (
                    f"MCP server did not advertise declared resource {resource_name}."
                )
        elif any(
            resource.name == resource_name or resource.uri == resource_uri
            for resource in result.resources
        ):
            return f"MCP server advertised undeclared resource {resource_name}."

        try:
            response = await client.read_resource(resource_uri)
        except MCPError as error:
            if not declared and error.code == -32002:
                return None
            raise
        if not declared:
            if response.contents:
                return (
                    "MCP server returned content for undeclared resource "
                    f"{resource_name}."
                )
            return None

        if len(response.contents) != 1:
            return f"{resource_name} did not return exactly one resource content block."
        content = response.contents[0]
        if (
            not isinstance(content, types.TextResourceContents)
            or content.uri != resource_uri
            or content.mime_type != "text/plain"
            or content.text != expected_greeting
        ):
            return (
                f"{resource_name} returned an unexpected URI, MIME type, "
                "or text greeting."
            )
        return None

    return _run_mcp_probe(
        probe_context, "test_resource_2_matches_declaration", _operation
    )


def test_resource_3_matches_declaration(probe_context: ProbeContext) -> ProbeResult:
    """Verify test_resource_3 is listed and readable only when declared."""
    resource_name = "test_resource_3"
    resource_uri = "metisa://test_resource_3"
    expected_greeting = "Hello, from test_resource_3."
    mcp_server = probe_context.specification.mcp_server
    declared = mcp_server is not None and resource_name in mcp_server.resources

    async def _operation(client: Client) -> str | None:
        from mcp import types
        from mcp.shared.exceptions import MCPError

        result = await client.list_resources()
        if declared:
            if not any(
                resource.name == resource_name and resource.uri == resource_uri
                for resource in result.resources
            ):
                return (
                    f"MCP server did not advertise declared resource {resource_name}."
                )
        elif any(
            resource.name == resource_name or resource.uri == resource_uri
            for resource in result.resources
        ):
            return f"MCP server advertised undeclared resource {resource_name}."

        try:
            response = await client.read_resource(resource_uri)
        except MCPError as error:
            if not declared and error.code == -32002:
                return None
            raise
        if not declared:
            if response.contents:
                return (
                    "MCP server returned content for undeclared resource "
                    f"{resource_name}."
                )
            return None

        if len(response.contents) != 1:
            return f"{resource_name} did not return exactly one resource content block."
        content = response.contents[0]
        if (
            not isinstance(content, types.TextResourceContents)
            or content.uri != resource_uri
            or content.mime_type != "text/plain"
            or content.text != expected_greeting
        ):
            return (
                f"{resource_name} returned an unexpected URI, MIME type, "
                "or text greeting."
            )
        return None

    return _run_mcp_probe(
        probe_context, "test_resource_3_matches_declaration", _operation
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
        return ProbeResult.failure(probe_name, f"MCP operation failed: {details}")
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
            _MCP_SERVER_ALIAS, str(_MCP_SERVER_PORT), type=socket.SOCK_STREAM
        )
    return {str(address[4][0]) for address in addresses}


MCP_PROBES = ProbeGroup(
    name="mcp",
    probes=(
        mcp_server_alias_resolves,
        test_tool_1_is_available,
        test_tool_1_returns_expected_greeting,
        test_tool_2_returns_expected_greetings,
        test_tool_2_rejects_non_string_name,
        test_tool_2_rejects_additional_arguments,
        test_tool_3_validates_name,
        test_tool_3_rejects_non_string_name,
        test_tool_3_rejects_additional_arguments,
        test_resource_1_is_available,
        test_resource_1_returns_expected_greeting,
        test_resource_2_matches_declaration,
        test_resource_3_matches_declaration,
    ),
)
