"""Internet access tests for the sample agent."""

from __future__ import annotations

import requests

from metisa_common.specification_models import (
    Capability,
    MetisaSpecification,
)

from .._helper import (
    get_mcp_server_tool_result,
    print_caution,
    print_disabled,
    print_elapsed_time,
    print_failure,
    print_success,
    print_suite_title,
)

_SKIP_INTERNET_TESTS = False


def test_internet_access(specification: MetisaSpecification):
    """Run internet access tests."""
    print_suite_title("Internet")

    if _SKIP_INTERNET_TESTS:
        print_caution("Internet capability is being skipped.")
        return

    if Capability.INTERNET not in specification.capabilities:
        print_disabled("Internet capability not declared.")
        return

    url = "https://example.com"
    if Capability.MCP_SERVER in specification.capabilities:
        _test_mcp_internet_access(specification, url)
    else:
        _test_direct_internet_access(specification, url)


def _test_direct_internet_access(
    specification: MetisaSpecification,
    url: str,
) -> None:
    with print_elapsed_time():
        if Capability.LLM_BROKER in specification.capabilities:
            try:
                url_title, url_error = _get_url_title_directly(url)
                if url_error:
                    print_failure(f"URL title directly, error: {url_error}")
                else:
                    print_success(f"URL title directly: '{url_title}'")
            except Exception:
                print_success(
                    "Workload container was disallowed to connect to the internet"
                )
        else:
            try:
                url_title, url_error = _get_url_title_directly(url)
                if url_error:
                    print_failure(f"URL title directly, error: {url_error}")
                else:
                    print_success(f"URL title directly: '{url_title}'")
            except Exception as error:
                print_failure("Internet connection exception", error)


def _test_mcp_internet_access(
    specification: MetisaSpecification,
    url: str,
) -> None:
    with print_elapsed_time():
        try:
            url_title = get_mcp_server_tool_result(
                tool_name="get_title_from_url",
                params={"url": url},
            )
            print_success(f"URL title from MCP Server: '{url_title}'")
        except Exception as error:
            print_failure("URL title from MCP Server error:", error)


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
