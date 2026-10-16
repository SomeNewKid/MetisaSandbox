"""Probe local LLM readiness and the LLM Broker's declared model catalog."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import urllib.parse
import urllib.request
from collections.abc import Callable

from metisa_common.specification_models import Capability, LlmModel

from ..probe_models import ProbeContext, ProbeGroup, ProbeResult

_LLM_BROKER_ALIAS = "metisa-llm-broker"
_LLM_BROKER_PORT = 8000
_LLM_BROKER_URL = f"http://{_LLM_BROKER_ALIAS}:{_LLM_BROKER_PORT}"
_TIMEOUT_SECONDS = 5


def llm_broker_alias_resolves(probe_context: ProbeContext) -> ProbeResult:
    """Verify the broker alias resolves to non-loopback addresses."""
    probe_name = "container__llm__broker_alias_resolves"
    if Capability.LLM_BROKER not in probe_context.specification.capabilities:
        return ProbeResult.success(
            probe_name, "LLM broker capability is disabled. Skipping probe."
        )

    try:
        addresses = asyncio.run(_resolve_alias())
        if not addresses:
            return ProbeResult.failure(probe_name, "Broker alias did not resolve.")
        if any(ipaddress.ip_address(address).is_loopback for address in addresses):
            return ProbeResult.failure(
                probe_name, "Broker alias resolved to a loopback address."
            )
    except Exception as error:
        return ProbeResult.failure(
            probe_name, f"Broker alias resolution failed: {error}"
        )

    return ProbeResult.success(
        probe_name, "Broker alias resolves to sidecar addresses."
    )


def llm_servers_are_ready(probe_context: ProbeContext) -> ProbeResult:
    """Verify the broker reports readiness for every declared local model."""
    return _run_llm_probe(probe_context, "servers_are_ready", _check_readiness)


def llm_models_are_available(probe_context: ProbeContext) -> ProbeResult:
    """Verify the broker advertises its declared local and online model aliases."""
    probe_name = "container__llm__models_are_available"
    specification = probe_context.specification
    if Capability.LLM_BROKER not in specification.capabilities:
        return ProbeResult.success(
            probe_name, "LLM broker capability is disabled. Skipping probe."
        )

    llm_broker = specification.llm_broker
    if llm_broker is None:
        return ProbeResult.failure(
            probe_name, "LLM broker capability requires an LLM broker specification."
        )

    expected_aliases = set(llm_broker.local_models)
    expected_aliases.update(llm_broker.online_models)
    try:
        failure = _check_models(expected_aliases)
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"

    if failure is not None:
        return ProbeResult.failure(probe_name, f"{_LLM_BROKER_URL}: {failure}")
    return ProbeResult.success(
        probe_name, f"Checked {len(expected_aliases)} broker-declared LLM models."
    )


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

    if Capability.LLM_BROKER not in specification.capabilities:
        return ProbeResult.failure(
            probe_name, "Local LLM model probes require the LLM broker capability."
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
            failures.append(f"{model.alias} ({_LLM_BROKER_URL}): {failure}")

    if failures:
        return ProbeResult.failure(probe_name, "; ".join(failures))
    return ProbeResult.success(
        probe_name, f"Checked {len(llm_server.models)} declared LLM models."
    )


async def _resolve_alias() -> set[str]:
    async with asyncio.timeout(_TIMEOUT_SECONDS):
        loop = asyncio.get_running_loop()
        addresses = await loop.getaddrinfo(
            _LLM_BROKER_ALIAS, _LLM_BROKER_PORT, type=socket.SOCK_STREAM
        )
    return {str(address[4][0]) for address in addresses}


def _check_readiness(model: LlmModel) -> str | None:
    model_alias = urllib.parse.quote(model.alias, safe="")
    response = _request_json(f"/health/{model_alias}")
    if response.get("status") != "ok":
        return "Broker model health endpoint did not report status 'ok'."
    if response.get("model") != model.alias:
        return f"Broker model health response did not match alias {model.alias!r}."
    return None


def _check_models(expected_aliases: set[str]) -> str | None:
    response = _request_json("/v1/models")
    models = response.get("data")
    if not isinstance(models, list):
        return "Broker model listing did not contain a model array."
    advertised_aliases: set[str] = set()
    for advertised_model in models:
        if not isinstance(advertised_model, dict):
            return "Broker model listing contained an invalid model object."
        alias = advertised_model.get("id")
        if not isinstance(alias, str) or not alias:
            return "Broker model listing contained an invalid model identifier."
        advertised_aliases.add(alias)
    missing_aliases = expected_aliases - advertised_aliases
    if missing_aliases:
        missing_names = ", ".join(sorted(missing_aliases))
        return f"Broker model listing is missing expected aliases: {missing_names}."
    return None


def _request_json(
    endpoint: str,
) -> dict[str, object]:
    url = f"{_LLM_BROKER_URL}{endpoint}"
    headers = {"Accept": "application/json"}
    request = urllib.request.Request(url, headers=headers)
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
        llm_broker_alias_resolves,
        llm_servers_are_ready,
        llm_models_are_available,
    ),
)
