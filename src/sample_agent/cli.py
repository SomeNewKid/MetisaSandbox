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

from metisa_common.specification_helper import (
    load_specification,
)
from metisa_common.specification_models import (
    Capability,
    MetisaSpecification,
)

root_directory = Path(__file__).parent
metisa_json_path = root_directory / "metisa.toml"
if not metisa_json_path.is_file():
    raise FileNotFoundError("Sample Agent missing a metisa.toml file.")
specification: MetisaSpecification = load_specification(metisa_json_path)

IS_INTERACTIVE = Capability.INTERACTIVE in specification.capabilities


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

    if Capability.INTERNET in specification.capabilities:
        try:
            print()
            print("-" * 30)
            url_title, url_error = _get_url_title_directly(url)
            if url_error:
                print(f"URL title directly, error: {url_error}")
            else:
                print(f"URL title directly: '{url_title}'")
        except Exception as error:
            print("Internet connection exception", error)

    if Capability.MCP_SERVER in specification.capabilities:
        if Capability.INTERNET in specification.capabilities:
            try:
                print()
                print("-" * 30)
                url_title = _get_url_title_from_mcp_server(url)
                print(f"URL title from MCP Server: '{url_title}'")
            except Exception as error:
                print("MCP server error:", error)

            if Capability.JINA_READER in specification.capabilities:
                try:
                    print()
                    print("-" * 30)
                    url_content = _get_url_content_from_mcp_server(url)
                    print(f"URL content from MCP Server: {url_content}")
                except Exception as error:
                    print("MCP server error:", error)

        if Capability.LOCALNET in specification.capabilities:
            try:
                print()
                print("-" * 30)
                active_items = _get_active_items()
                print("Database records from MCP server:", active_items)
            except Exception as error:
                print("MCP server error:", error)

    if Capability.LLM_SERVER in specification.capabilities:
        prompt_for_llm = "Explain Docker networks in two sentences."

        try:
            print()
            print("-" * 30)
            print("To Granite:", prompt_for_llm)
            answer_from_llm = _get_granite_response("granite-4-1b", prompt_for_llm)
            print("From Granite:", answer_from_llm)
        except Exception as error:
            print("Granite error:", error)

        try:
            print()
            print("-" * 30)
            print("To Qwen:", prompt_for_llm)
            answer_from_llm = _get_qwen_response("qwen-3-small", prompt_for_llm)
            print("From Qwen:", answer_from_llm)
        except Exception as error:
            print("Qwen error:", error)

    print()
    print("-" * 30)

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
            trust_env = False

            async with httpx2.AsyncClient(
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

    if len(result.content) != 1:
        raise RuntimeError("Expected exactly one tool content block.")

    content = result.content[0]
    if not isinstance(content, types.TextContent):
        actual_type = type(content)
        raise RuntimeError(f"Expected a text result from {tool_name}. {actual_type}")

    return content.text


def _get_granite_response(
    llm_alias: str,
    prompt: str,
) -> str:
    with requests.Session() as session:
        # Private-network requests must bypass the internet proxy.
        session.trust_env = False

        try:
            response = session.post(
                f"http://metisa-llm-{llm_alias}:8080/v1/chat/completions",
                json={
                    "model": llm_alias,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    "max_tokens": 128,
                    "stream": False,
                },
                timeout=(5, 600),
            )
            response.raise_for_status()
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            return answer
        except (requests.RequestException, ValueError, KeyError, IndexError) as error:
            raise RuntimeError(
                f"LLM request to '{llm_alias}' failed:", error
            ) from error


def _get_qwen_response(
    llm_alias: str,
    prompt: str,
) -> str:
    with requests.Session() as session:
        # Private-network requests must bypass the internet proxy.
        session.trust_env = False

        try:
            response = session.post(
                f"http://metisa-llm-{llm_alias}:8080/v1/chat/completions",
                json={
                    "model": llm_alias,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    "chat_template_kwargs": {"enable_thinking": False},
                    "max_tokens": 128,
                    "stream": False,
                },
                timeout=(5, 600),
            )
            response.raise_for_status()
            result = response.json()

            choice = result["choices"][0]

            # print("Qwen message:", choice["message"])
            # print("Qwen finish reason:", choice.get("finish_reason"))
            # print("Qwen usage:", result.get("usage"))

            return choice["message"]["content"]
        except (requests.RequestException, ValueError, KeyError, IndexError) as error:
            raise RuntimeError(
                f"LLM request to '{llm_alias}' failed:", error
            ) from error
