"""Provide the tool which executes Starlark code."""

from __future__ import annotations

import json
from typing import Annotated

import requests
from jsonschema import ValidationError, validate
from pydantic import Field

from .._errors import KnownSafeError
from .._helper import with_output_schema

_TOOL_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "result": {"type": "string"},
    },
    "required": ["result"],
    "additionalProperties": False,
}


@with_output_schema(_TOOL_RESULT_SCHEMA)
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
) -> dict[str, object]:
    """Return the result of executing the provided Starlark code."""
    _validate_arguments(starlark_code)

    result = _execute_tool(starlark_code)

    _validate_result(result)

    return result


def _validate_arguments(
    starlark_code: str,
) -> None:
    if not starlark_code:
        raise ValueError("Starlark code must be provided.")


def _execute_tool(
    starlark_code: str,
) -> dict[str, object]:
    starlark_endpoint = "http://metisa-code-execution:8090/execute"
    headers = {"Accept": "application/json"}
    payload = {"code": starlark_code}

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
    except requests.RequestException as error:
        raise RuntimeError("Starlark request failed.") from error

    try:
        dictionary = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise RuntimeError("Starlark returned invalid JSON.") from error

    if not isinstance(dictionary, dict):
        raise RuntimeError("Starlark did not return a JSON dictionary.")

    error_result = dictionary.get("error")
    if error_result is not None:
        if not isinstance(error_result, str):
            raise RuntimeError("Starlark returned an invalid error.")

        remote_error = RuntimeError(error_result)

        if error_result in (
            "script must define main()",
            "Starlark computation cancelled: too many steps",
        ):
            raise KnownSafeError(error_result) from remote_error

        # Preserve the remote message as the cause while returning a fixed outer message
        raise RuntimeError("Starlink execution failed.") from remote_error

    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        raise RuntimeError("Starlark returned an HTTP error.") from error

    result = dictionary.get("result")
    if not isinstance(result, str):
        raise RuntimeError("Starlark did not return a string result.")

    return {"result": result}


def _validate_result(
    result: dict[str, object],
) -> None:
    try:
        validate(result, _TOOL_RESULT_SCHEMA)
    except ValidationError as error:
        error_message = "Starlark returned content in an unexpected format."
        raise RuntimeError(error_message) from error
