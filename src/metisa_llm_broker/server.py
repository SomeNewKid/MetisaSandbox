"""Implememnt the LLM Broker."""

from __future__ import annotations

import http.client
import json
import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

root_directory = Path(__file__).parent
metisa_json_file = root_directory.with_name("metisa.json")

if not metisa_json_file.exists():
    raise RuntimeError("Metisa JSON file not found.")

with metisa_json_file.open("r", encoding="utf-8") as file:
    metisa_json = json.load(file)

if not isinstance(metisa_json, dict):
    raise RuntimeError("Invalid Metisa JSON file.")

local_models = metisa_json.get("local_models")
if not isinstance(local_models, list):
    raise RuntimeError("Metisa JSON local_models must be an array.")

for alias in local_models:
    if not isinstance(alias, str) or not alias:
        raise RuntimeError("Metisa JSON model aliases must be non-empty strings.")

online_models = metisa_json.get("online_models")
if not isinstance(online_models, list):
    raise RuntimeError("Metisa JSON online_models must be an array.")

for alias in online_models:
    if not isinstance(alias, str) or not alias:
        raise RuntimeError("Metisa JSON model aliases must be non-empty strings.")

_LOCAL_MODEL_ALIASES = frozenset(local_models)
_ONLINE_MODEL_ALIASES = frozenset(online_models)
_LLM_SERVER_PREFIX = "metisa-llm-"
_LLM_SERVER_PORT = 8080
_SQUID_PROXY_HOST = "metisa-squid"
_SQUID_PROXY_PORT = 3128
_HEALTH_TIMEOUT_SECONDS = 30
_MAX_HEALTH_RESPONSE_BYTES = 64 * 1024

_CHAT_TIMEOUT_SECONDS = 600
_MAX_CHAT_REQUEST_BYTES = 1024 * 1024
_MAX_CHAT_RESPONSE_BYTES = 4 * 1024 * 1024

_CHAT_REQUEST_FIELDS = frozenset(
    {
        "model",
        "messages",
        "stream",
        "max_tokens",
        "max_completion_tokens",
        "temperature",
        "top_p",
        "stop",
        "seed",
    }
)
_LLAMA_CPP_REQUEST_FIELDS = frozenset(
    {
        "chat_template_kwargs",
    }
)

_CHAT_MESSAGE_ROLES = frozenset({"system", "developer", "user", "assistant"})

_RESPONSES_TIMEOUT_SECONDS = 600
_MAX_RESPONSES_REQUEST_BYTES = 1024 * 1024
_MAX_RESPONSES_RESPONSE_BYTES = 4 * 1024 * 1024

_RESPONSES_REQUEST_FIELDS = frozenset(
    {
        "model",
        "input",
        "instructions",
        "stream",
        "store",
        "max_output_tokens",
        "temperature",
        "top_p",
    }
)

_RESPONSES_MESSAGE_ROLES = frozenset({"system", "developer", "user", "assistant"})


async def _health(
    _request: Request,
) -> PlainTextResponse:
    return PlainTextResponse("OK", status_code=200)


def _model_health(
    request: Request,
) -> JSONResponse:
    model_alias = request.path_params["alias"]

    if model_alias not in _LOCAL_MODEL_ALIASES:
        if model_alias in _ONLINE_MODEL_ALIASES:
            return JSONResponse(
                {
                    "model": model_alias,
                    "error": (
                        "Online model aliases are not supported for health checks."
                    ),
                },
                status_code=400,
            )
        return JSONResponse(
            {"model": model_alias, "error": "Unknown model alias."},
            status_code=404,
        )

    hostname = f"{_LLM_SERVER_PREFIX}{model_alias}"
    connection = http.client.HTTPConnection(
        hostname,
        _LLM_SERVER_PORT,
        timeout=_HEALTH_TIMEOUT_SECONDS,
    )

    try:
        connection.request("GET", "/health")
        response = connection.getresponse()

        if response.status != 200:
            return JSONResponse(
                {"model": model_alias, "status": "unavailable"},
                status_code=503,
            )

        body = response.read(_MAX_HEALTH_RESPONSE_BYTES + 1)
        if len(body) > _MAX_HEALTH_RESPONSE_BYTES:
            return JSONResponse(
                {"model": model_alias, "error": "Health response is too large."},
                status_code=502,
            )

        payload = json.loads(body)
        if not isinstance(payload, dict):
            return JSONResponse(
                {"model": model_alias, "error": "Invalid health response."},
                status_code=502,
            )

        if payload.get("status") != "ok":
            return JSONResponse(
                {"model": model_alias, "status": "unavailable"},
                status_code=503,
            )

        payload["model"] = model_alias
        return JSONResponse(payload, status_code=200)

    except (OSError, http.client.HTTPException):
        return JSONResponse(
            {"model": model_alias, "status": "unavailable"},
            status_code=503,
        )

    except (ValueError, UnicodeDecodeError):
        return JSONResponse(
            {"model": model_alias, "error": "Invalid health response."},
            status_code=502,
        )

    finally:
        connection.close()


# https://developers.openai.com/api/reference/resources/models/methods/list
async def _v1_models(
    _request: Request,
) -> JSONResponse:
    data = []
    for alias in _LOCAL_MODEL_ALIASES | _ONLINE_MODEL_ALIASES:
        data.append(
            {
                "id": alias,
                "object": "model",
                "created": 0,  # Creation time as a Unix timestamp in seconds
                "owned_by": "metisa",  # Okay for internal broker catalog
            }
        )
    payload = {
        "object": "list",
        "data": data,
    }
    return JSONResponse(payload, status_code=200)


# https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
async def _v1_chat_completions(
    request: Request,
) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";")[0].strip().lower()
    if media_type != "application/json":
        return _chat_error("Expected application/json.", 415)

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > _MAX_CHAT_REQUEST_BYTES:
            return _chat_error("Request body is too large.", 413)
        body.extend(chunk)

    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return _chat_error("Expected valid JSON.", 400)

    if not isinstance(payload, dict):
        return _chat_error("Expected a JSON object.", 400)

    model_alias = payload.get("model")
    if not isinstance(model_alias, str) or not model_alias:
        return _chat_error("model must be a non-empty string.", 400)

    if model_alias not in _LOCAL_MODEL_ALIASES | _ONLINE_MODEL_ALIASES:
        return _chat_error("Unknown model alias.", 404)

    allowed_fields = _CHAT_REQUEST_FIELDS | _LLAMA_CPP_REQUEST_FIELDS
    unknown_fields = payload.keys() - allowed_fields

    if unknown_fields:
        return _chat_error("Request contains unsupported fields.", 400)

    if payload.get("stream", False) is not False:
        return _chat_error("Only non-streaming requests are supported.", 400)

    if "chat_template_kwargs" in payload:
        options = payload["chat_template_kwargs"]
        if not isinstance(options, dict):
            return _chat_error("chat_template_kwargs must be an object.", 400)

        validation_error = _validate_chat_template_kwargs(model_alias, options)
        if validation_error is not None:
            return _chat_error(validation_error, 400)

    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return _chat_error("messages must be a non-empty array.", 400)

    for message in messages:
        if not isinstance(message, dict):
            return _chat_error("Each message must be an object.", 400)

        if message.keys() - {"role", "content"}:
            return _chat_error("Message contains unsupported fields.", 400)

        role = message.get("role")
        if not isinstance(role, str) or role not in _CHAT_MESSAGE_ROLES:
            return _chat_error("Unsupported message role.", 400)

        if not isinstance(message.get("content"), str):
            return _chat_error("Message content must be text.", 400)

    payload["stream"] = False

    # Request inspection and permitted transformations

    try:
        serialized_payload = json.dumps(payload, allow_nan=False)
        downstream_body = serialized_payload.encode("utf-8")
    except ValueError:
        return _chat_error("Request contains invalid JSON values.", 400)

    return await run_in_threadpool(
        _get_downstream_chat_completion_response,
        model_alias,
        downstream_body,
    )


def _get_downstream_chat_completion_response(
    model_alias: str,
    downstream_body: bytes,
) -> JSONResponse:
    connection = _create_connection(model_alias, _CHAT_TIMEOUT_SECONDS)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    authorization_bearer = _get_authorization_bearer(model_alias)
    if authorization_bearer is not None:
        headers["Authorization"] = f"Bearer {authorization_bearer}"

    try:
        connection.request(
            "POST",
            "/v1/chat/completions",
            body=downstream_body,
            headers=headers,
        )
        response = connection.getresponse()

        if response.status != 200:
            if response.status in {400, 413, 422, 429, 503}:
                return _chat_error(
                    "Model server rejected the request.",
                    response.status,
                )
            return _chat_error("Model server returned an error.", 502)

        response_body = response.read(_MAX_CHAT_RESPONSE_BYTES + 1)
        if len(response_body) > _MAX_CHAT_RESPONSE_BYTES:
            return _chat_error("Model response is too large.", 502)

        payload = json.loads(response_body)
        if not isinstance(payload, dict):
            return _chat_error("Invalid model response.", 502)

        if payload.get("object") != "chat.completion":
            return _chat_error("Unexpected model response type.", 502)

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return _chat_error("Model response has no completion choices.", 502)

        # Inspect the complete response and apply permitted transformations.

        payload["model"] = model_alias
        return JSONResponse(payload, status_code=200)

    except TimeoutError:
        return _chat_error("Model request timed out.", 504)

    except (OSError, http.client.HTTPException):
        return _chat_error("Could not communicate with model server.", 502)

    except (ValueError, UnicodeDecodeError):
        return _chat_error("Invalid JSON response from model server.", 502)

    finally:
        connection.close()


async def _v1_responses(request: Request) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";")[0].strip().lower()
    if media_type != "application/json":
        return _chat_error("Expected application/json.", 415)

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > _MAX_RESPONSES_REQUEST_BYTES:
            return _chat_error("Request body is too large.", 413)
        body.extend(chunk)

    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return _chat_error("Expected valid JSON.", 400)

    if not isinstance(payload, dict):
        return _chat_error("Expected a JSON object.", 400)

    model_alias = payload.get("model")
    if not isinstance(model_alias, str) or not model_alias:
        return _chat_error("model must be a non-empty string.", 400)

    if model_alias not in _LOCAL_MODEL_ALIASES | _ONLINE_MODEL_ALIASES:
        return _chat_error("Unknown model alias.", 404)

    unknown_fields = payload.keys() - _RESPONSES_REQUEST_FIELDS
    if unknown_fields:
        return _chat_error("Request contains unsupported fields.", 400)

    if payload.get("stream", False) is not False:
        return _chat_error("Only non-streaming requests are supported.", 400)

    if payload.get("store", False) is not False:
        return _chat_error("Stored responses are not supported.", 400)

    if "instructions" in payload:
        if not isinstance(payload["instructions"], str):
            return _chat_error("instructions must be text.", 400)

    input_error = _validate_response_input(payload.get("input"))
    if input_error is not None:
        return _chat_error(input_error, 400)

    if "max_output_tokens" in payload:
        token_limit = payload["max_output_tokens"]
        if type(token_limit) is not int or token_limit <= 0:
            return _chat_error(
                "max_output_tokens must be a positive integer.",
                400,
            )

    payload["stream"] = False
    payload["store"] = False

    # Inspect input, instructions, and other permitted request fields

    try:
        serialized_payload = json.dumps(payload, allow_nan=False)
        downstream_body = serialized_payload.encode("utf-8")
    except ValueError:
        return _chat_error("Request contains invalid JSON values.", 400)

    return await run_in_threadpool(
        _get_downstream_responses_response,
        model_alias,
        downstream_body,
    )


def _get_downstream_responses_response(
    model_alias: str,
    downstream_body: bytes,
) -> JSONResponse:
    connection = _create_connection(model_alias, _RESPONSES_TIMEOUT_SECONDS)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    authorization_bearer = _get_authorization_bearer(model_alias)
    if authorization_bearer is not None:
        headers["Authorization"] = f"Bearer {authorization_bearer}"

    try:
        connection.request(
            "POST",
            "/v1/responses",
            body=downstream_body,
            headers=headers,
        )
        response = connection.getresponse()

        if response.status != 200:
            if response.status in {400, 413, 422, 429, 503}:
                return _chat_error(
                    "Model server rejected the request.",
                    response.status,
                )
            return _chat_error("Model server returned an error.", 502)

        response_body = response.read(_MAX_RESPONSES_RESPONSE_BYTES + 1)
        if len(response_body) > _MAX_RESPONSES_RESPONSE_BYTES:
            return _chat_error("Model response is too large.", 502)

        payload = json.loads(response_body)
        if not isinstance(payload, dict):
            return _chat_error("Invalid model response.", 502)

        if payload.get("object") != "response":
            return _chat_error("Unexpected model response type.", 502)

        if not isinstance(payload.get("output"), list):
            return _chat_error("Model response has no output array.", 502)

        if payload.get("status") not in ("completed", "incomplete", "failed"):
            return _chat_error("Unexpected model response status.", 502)

        # Inspect all output items before releasing the response.

        payload["model"] = model_alias
        return JSONResponse(payload, status_code=200)

    except TimeoutError:
        return _chat_error("Model request timed out.", 504)

    except (OSError, http.client.HTTPException):
        return _chat_error("Could not communicate with model server.", 502)

    except (ValueError, UnicodeDecodeError):
        return _chat_error("Invalid JSON response from model server.", 502)

    finally:
        connection.close()


def _validate_response_input(
    value: object,
) -> str | None:
    if isinstance(value, str):
        return None

    if not isinstance(value, list) or not value:
        return "input must be text or a non-empty array of text messages."

    for message in value:
        if not isinstance(message, dict):
            return "Each input message must be an object."

        if message.keys() - {"type", "role", "content"}:
            return "Input message contains unsupported fields."

        if message.get("type", "message") != "message":
            return "Only message input items are supported."

        role = message.get("role")
        if not isinstance(role, str) or role not in _RESPONSES_MESSAGE_ROLES:
            return "Unsupported input message role."

        if not isinstance(message.get("content"), str):
            return "Input message content must be text."

    return None


def _chat_error(
    message: str,
    status_code: int,
) -> JSONResponse:
    return JSONResponse(
        {
            "error": {
                "message": message,
                "type": "broker_error",
                "param": None,
                "code": None,
            }
        },
        status_code=status_code,
    )


def _validate_chat_template_kwargs(
    model_alias: str,
    options: dict[str, object],
) -> str | None:
    option_keys = options.keys()

    if model_alias == "qwen-3-small":
        unknown_options = option_keys - {"enable_thinking"}
        if unknown_options:
            return "Unsupported chat template options."

        if "enable_thinking" in options:
            if not isinstance(options["enable_thinking"], bool):
                return "enable_thinking must be a boolean."

        return None

    # Unknown model
    if option_keys:
        return "Unsupported chat template options."

    return None


def _create_connection(
    model_alias: str,
    timeout_seconds: int,
) -> http.client.HTTPConnection:
    if model_alias in _LOCAL_MODEL_ALIASES:
        return http.client.HTTPConnection(
            f"{_LLM_SERVER_PREFIX}{model_alias}",
            _LLM_SERVER_PORT,
            timeout=timeout_seconds,
        )

    # http.client does not automatically use HTTP_PROXY or HTTPS_PROXY
    # To route requests through the proxy, we manually set up the tunnel to the target.
    # https://docs.python.org/3.12/library/http.client.html#http.client.HTTPConnection.set_tunnel
    hostname = _get_hostname(model_alias)
    if not hostname:
        raise RuntimeError(f"Hostname not resolved for '{model_alias}'")
    port = _get_port(model_alias)

    connection = http.client.HTTPSConnection(
        _SQUID_PROXY_HOST,
        _SQUID_PROXY_PORT,
        timeout=timeout_seconds,
    )
    connection.set_tunnel(hostname, port)

    return connection


def _get_hostname(model_alias: str) -> str | None:
    if model_alias in _LOCAL_MODEL_ALIASES:
        return f"{_LLM_SERVER_PREFIX}{model_alias}"
    if model_alias in _ONLINE_MODEL_ALIASES:
        match model_alias:
            case "gpt-4o":
                return "api.openai.com"
            case _:
                return None
    return None


def _get_port(model_alias: str) -> int:
    if model_alias in _LOCAL_MODEL_ALIASES:
        return _LLM_SERVER_PORT
    return 443


def _get_authorization_bearer(
    model_alias: str,
) -> str | None:
    match model_alias:
        case "gpt-4o":
            return os.getenv("OPENAI_API_KEY")
        case _:
            return None


app = Starlette(
    routes=[
        Route(
            "/health",
            methods=["GET"],
            endpoint=_health,
        ),
        Route(
            "/health/{alias}",
            methods=["GET"],
            endpoint=_model_health,
        ),
        Route(
            "/v1/models",
            methods=["GET"],
            endpoint=_v1_models,
        ),
        Route(
            "/v1/chat/completions",
            methods=["POST"],
            endpoint=_v1_chat_completions,
        ),
        Route(
            "/v1/responses",
            endpoint=_v1_responses,
            methods=["POST"],
        ),
    ]
)
