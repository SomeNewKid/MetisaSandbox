"""Utility functions for working with the MCP Server."""

from __future__ import annotations

import asyncio

import httpx2
from mcp import Client, types
from mcp.client.streamable_http import streamable_http_client
from opentelemetry import trace
from opentelemetry.propagate import inject
from opentelemetry.trace import SpanKind

from metisa_common.secrets_helper import (
    load_secrets,
)


def get_mcp_server_tool_result(
    tool_name: str,
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    """Get the result of calling a tool on the MCP Server."""
    tracer = trace.get_tracer("sample_agent.tools")

    with tracer.start_as_current_span(
        f"tool.call {tool_name}",
        kind=SpanKind.CLIENT,
        attributes={"metisa.tool.name": tool_name},
    ):
        return _get_mcp_server_tool_result(tool_name, params)


def _get_mcp_server_tool_result(
    tool_name: str,
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    """Get the result of calling a tool on the MCP Server."""
    url = "http://metisa-mcp-server:8000/mcp"
    timeout_seconds = 300
    secrets = load_secrets()
    mcp_server_token = secrets["METISA_MCP_SERVER_TOKEN"]
    if not mcp_server_token:
        raise RuntimeError("METISA_MCP_SERVER_TOKEN secret is not set.")

    async def _call() -> types.CallToolResult:
        async with asyncio.timeout(timeout_seconds):
            # private-network traffic cannot use workload's internet proxy
            trust_env = False
            headers: dict[str, str] = {
                "Authorization": f"Bearer {mcp_server_token}",
            }

            # read the current tool span and add trace-context headers
            inject(headers)

            async with httpx2.AsyncClient(
                headers=headers,
                trust_env=trust_env,
                timeout=timeout_seconds,
            ) as http_client:
                transport = streamable_http_client(
                    url=url,
                    http_client=http_client,
                )
                async with Client(
                    transport,
                    read_timeout_seconds=timeout_seconds,
                ) as client:
                    arguments = params or {}
                    return await client.call_tool(tool_name, arguments)

    result = asyncio.run(_call())

    if result.is_error:
        details = "\n".join(
            content.text
            for content in result.content
            if isinstance(content, types.TextContent)
        )
        raise RuntimeError(details or f"{tool_name} failed.")

    payload = result.structured_content
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected a structured JSON object from {tool_name}.")

    return payload
