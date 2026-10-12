"""Command-line interface for the application."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path

import httpx2
import requests
from mcp import Client, types
from mcp.client.streamable_http import streamable_http_client

IS_INTERACTIVE = False


def main(
    argv: list[str] | None = None,
) -> int:
    """Run the sample agent workload."""
    output_dir = os.environ.get("SANDBOX_OUTPUT_DIR", "")
    is_running_local = not output_dir
    if is_running_local:
        output_dir = _create_run_directory()
    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)

    if IS_INTERACTIVE:
        user_name = input("What is your name? ")
    else:
        user_name = "Fred"

    message = f"Hello {user_name} from the Sample Agent."

    answer_path = output_directory / "answer.txt"
    answer_path.write_text(
        message,
        encoding="utf-8",
    )

    print(message)
    print(f"Wrote answer to {answer_path}")

    url = "https://example.com"
    try:
        url_title, url_error = _get_url_title_directly(url)
        if url_error:
            print(f"URL title directly, error: {url_error}")
        else:
            print(f"URL title directly: '{url_title}'")
    except Exception as error:
        print("Internet connection exception", error)

    try:
        url_title = _get_url_title_from_mcp_server(url)
        print(f"URL title from MCP Server: '{url_title}'")
    except Exception as error:
        print("MCP server error:", error)

    try:
        url_content = _get_url_content_from_mcp_server(url)
        print(f"URL content from MCP Server: {url_content}")
    except Exception as error:
        print("MCP server error:", error)

    try:
        active_items = _get_active_items()
        print("Database records from MCP server:", active_items)
    except Exception as error:
        print("MCP server error:", error)

    return 0


# This function is only used when the agent is run without the sandbox.
def _create_run_directory() -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    run_directory = Path.cwd() / ".runs" / f"run-{timestamp}" / "output"
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_directory


def _get_url_title_directly(
    url: str,
) -> tuple[str, str]:
    title: str = ""
    error: str = ""
    response = requests.get(url)
    status_code = response.status_code
    if status_code == 200:
        html = response.text
        if html:
            title = _get_title_from_html(response.text)
            if not title:
                error = f"Could not get page title from {url}."
        else:
            error = "Received empty response."
    else:
        error = f"Failed to get response.  Status code: {status_code}"
    return title, error


def _get_title_from_html(
    html: str,
) -> str:
    tag = "title"
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    open_tag_index = html.find(open_tag)
    close_tag_index = html.find(close_tag)
    if open_tag_index < 0 or close_tag_index < 0:
        return ""
    return html[open_tag_index + len(open_tag) : close_tag_index]


def _get_active_items() -> str:
    return _get_mcp_server_tool_result("get_active_items")


def _get_url_title_from_mcp_server(
    url: str,
) -> str:
    return _get_mcp_server_tool_result("get_title_from_url", {"url": url})


def _get_url_content_from_mcp_server(
    url: str,
) -> str:
    return _get_mcp_server_tool_result("read_content_from_url", {"url": url})


def _get_mcp_server_tool_result(
    tool_name: str, params: dict[str, object] | None = None
) -> str:
    url = "http://metisa-mcp-server:8000/mcp"
    timeout_seconds = 30

    async def _call() -> types.CallToolResult:
        async with asyncio.timeout(timeout_seconds):
            # private-network traffic cannot use workload's internet proxy
            test_env = False

            async with httpx2.AsyncClient(
                trust_env=test_env,
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

    if len(result.content) != 1:
        raise RuntimeError("Expected exactly one tool content block.")

    content = result.content[0]
    if not isinstance(content, types.TextContent):
        actual_type = type(content)
        raise RuntimeError(f"Expected a text result from {tool_name}. {actual_type}")

    return content.text
