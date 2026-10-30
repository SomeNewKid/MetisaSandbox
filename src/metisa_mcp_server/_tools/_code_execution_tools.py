"""Provide the code execution tools for the Metisa MCP Server."""

from __future__ import annotations

import json
from typing import Annotated

import requests
from pydantic import Field

from .._helper import with_output_schema


@with_output_schema(
    {
        "type": "object",
        "properties": {
            "result": {"type": "string"},
        },
        "required": ["result"],
        "additionalProperties": False,
    }
)
def execute_starlark_code(
    starlark_code: Annotated[
        str,
        Field(
            description="""
        The Starlark code to be executed, 
        which must reside in a main() function with no parameters.
        For example:
        
        def main():
            values = [10, 20, 30]
            total = 0
            for value in values:
                total += value
            return total / len(values)
        """
        ),
    ],
) -> dict[str, object] | None:
    """Return the result of executing the provided Starlark code."""
    starlark_endpoint = "http://metisa-code-execution:8090/execute"
    headers = {
        "Accept": "application/json",
    }
    payload = {"code": starlark_code}

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                starlark_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 120),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Starlark did not return any content.")
        try:
            dictionary = json.loads(content)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Starlark returned an error: {content}") from error
        if not isinstance(dictionary, dict):
            raise RuntimeError("Starlark did not return expected JSON dictionary.")
        error_result = dictionary.get("error", None)
        if error_result is not None:
            raise RuntimeError(f"Starlark returned an error: {error_result}")
        result = dictionary.get("result", None)
        if result is None:
            raise RuntimeError("Starlark did not return expected JSON format.")
        if not isinstance(result, str):
            raise RuntimeError("Starlark did not return a string result.")
        return {
            "result": result,
        }
    except Exception as error:
        if content:
            raise RuntimeError(f"Starlark returned an error: {content}") from error
        raise RuntimeError(f"Starlark returned an error: {error}") from error
