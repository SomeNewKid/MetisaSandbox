"""Probes for declared local LLM server sidecars."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import urllib.request
from collections.abc import Callable

from metisa_common.specification_models import Capability, LlmModel

from ..probe_models import ProbeContext, ProbeGroup, ProbeResult

_LLM_SERVER_ALIAS_PREFIX = "metisa-llm-"
_LLM_SERVER_PORT = 8080
_TIMEOUT_SECONDS = 5


def llm_server_aliases_resolve(probe_context: ProbeContext) -> ProbeResult:
    """Verify every declared LLM alias resolves to non-loopback addresses."""
    return _run_llm_probe(probe_context, "aliases_resolve", _check_alias)


def llm_servers_are_ready(probe_context: ProbeContext) -> ProbeResult:
    """Verify every declared LLM server reports readiness without inference."""
    return _run_llm_probe(probe_context, "servers_are_ready", _check_readiness)


def llm_models_are_available(probe_context: ProbeContext) -> ProbeResult:
    """Verify every server advertises its declared model alias."""
    return _run_llm_probe(probe_context, "models_are_available", _check_model)


def llm_tokenizers_are_available(probe_context: ProbeContext) -> ProbeResult:
    """Verify every declared model tokenizes text without generating a response."""
    return _run_llm_probe(probe_context, "tokenizers_are_available", _check_tokenizer)


def _run_llm_probe(
    probe_context: ProbeContext,
    name: str,
    operation: Callable[[LlmModel], str | None],
) -> ProbeResult:
    probe_name = f"container__llm__{name}"
    specification = probe_context.specification
    if Capability.LLM_SERVER not in specification.capabilities:
        return ProbeResult.success(
            probe_name, "LLM server capability is disabled. Skipping probe."
        )

    llm_server = specification.llm_server
    if llm_server is None:
        return ProbeResult.failure(
            probe_name, "LLM server capability requires an LLM server specification."
        )

    failures: list[str] = []
    for model in llm_server.models:
        try:
            failure = operation(model)
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
        if failure is not None:
            server_url = _get_server_url(model)
            failures.append(f"{model.alias} ({server_url}): {failure}")

    if failures:
        return ProbeResult.failure(probe_name, "; ".join(failures))
    return ProbeResult.success(
        probe_name, f"Checked {len(llm_server.models)} declared LLM models."
    )


def _get_server_url(model: LlmModel) -> str:
    return f"http://{_LLM_SERVER_ALIAS_PREFIX}{model.alias}:{_LLM_SERVER_PORT}"


def _check_alias(model: LlmModel) -> str | None:
    addresses = asyncio.run(_resolve_alias(model))
    if not addresses:
        return "Network alias did not resolve to any addresses."
    if any(ipaddress.ip_address(address).is_loopback for address in addresses):
        return "Network alias resolved to a loopback address."
    return None


async def _resolve_alias(model: LlmModel) -> set[str]:
    network_alias = f"{_LLM_SERVER_ALIAS_PREFIX}{model.alias}"
    async with asyncio.timeout(_TIMEOUT_SECONDS):
        loop = asyncio.get_running_loop()
        addresses = await loop.getaddrinfo(
            network_alias, _LLM_SERVER_PORT, type=socket.SOCK_STREAM
        )
    return {str(address[4][0]) for address in addresses}


def _check_readiness(model: LlmModel) -> str | None:
    response = _request_json(model, "/health")
    if response.get("status") != "ok":
        return "Health endpoint did not report status 'ok'."
    return None


def _check_model(model: LlmModel) -> str | None:
    response = _request_json(model, "/v1/models")
    models = response.get("data")
    if not isinstance(models, list) or len(models) != 1:
        return "Model listing did not contain exactly one model."
    advertised_model = models[0]
    if not isinstance(advertised_model, dict):
        return "Model listing contained an invalid model object."
    if advertised_model.get("id") != model.alias:
        return f"Model listing did not advertise expected alias {model.alias!r}."
    return None


def _check_tokenizer(model: LlmModel) -> str | None:
    response = _request_json(
        model, "/tokenize", {"content": "Hello", "add_special": False}
    )
    tokens = response.get("tokens")
    if not isinstance(tokens, list) or not tokens:
        return "Tokenizer did not return a non-empty token array."
    if any(type(token) is not int or token < 0 for token in tokens):
        return "Tokenizer returned invalid token IDs."
    return None


def _request_json(
    model: LlmModel,
    endpoint: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    server_url = _get_server_url(model)
    url = f"{server_url}{endpoint}"
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    # Internal sidecar requests must bypass the workload's internet proxies.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise RuntimeError(f"{endpoint} returned HTTP {response.status}.")
        body = response.read()
    result = json.loads(body)
    if not isinstance(result, dict):
        raise ValueError(f"{endpoint} did not return a JSON object.")
    return result


LLM_PROBES = ProbeGroup(
    name="llm",
    probes=(
        llm_server_aliases_resolve,
        llm_servers_are_ready,
        llm_models_are_available,
        llm_tokenizers_are_available,
    ),
)
