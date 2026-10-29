import json
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from metisa_common.specification_models import Capability, LlmBrokerSpecification
from metisa_probes._container import _llm_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction


@pytest.fixture
def broker_context(probe_context: ProbeContext) -> ProbeContext:
    broker = LlmBrokerSpecification(
        frozenset(), frozenset(), ("local/model", "second"), ("online",)
    )
    return replace(
        probe_context,
        specification=replace(
            probe_context.specification,
            capabilities=frozenset({Capability.LLM_BROKER}),
            llm_broker=broker,
        ),
    )


@pytest.mark.parametrize("probe", probes.LLM_PROBES.probes)
def test_disabled_broker_skips(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, probe: ProbeFunction
) -> None:
    request = Mock(side_effect=AssertionError("unexpected request"))
    monkeypatch.setattr(probes, "_request_json", request)
    monkeypatch.setattr(probes, "_resolve_alias", request)
    result = probe(probe_context)
    assert result.passed
    assert "Skipping" in result.message
    request.assert_not_called()


@pytest.mark.parametrize(
    "addresses,passed",
    [
        ({"172.18.0.2"}, True),
        (set(), False),
        ({"127.0.0.1"}, False),
        ({"::1", "172.18.0.2"}, False),
        ({"invalid"}, False),
    ],
)
def test_broker_alias(
    monkeypatch: pytest.MonkeyPatch,
    broker_context: ProbeContext,
    addresses: set[str],
    passed: bool,
) -> None:
    monkeypatch.setattr(probes, "_resolve_alias", AsyncMock(return_value=addresses))
    assert probes.llm_broker_alias_resolves(broker_context).passed is passed


def test_broker_dns_error(
    monkeypatch: pytest.MonkeyPatch, broker_context: ProbeContext
) -> None:
    monkeypatch.setattr(
        probes, "_resolve_alias", AsyncMock(side_effect=OSError("DNS failed"))
    )
    assert not probes.llm_broker_alias_resolves(broker_context).passed


@pytest.mark.parametrize(
    "probe", [probes.llm_servers_are_ready, probes.llm_models_are_available]
)
def test_missing_broker_configuration(
    broker_context: ProbeContext, probe: ProbeFunction
) -> None:
    context = replace(
        broker_context,
        specification=replace(broker_context.specification, llm_broker=None),
    )
    assert not probe(context).passed


@pytest.mark.parametrize("mode", ["ready", "not_ready", "wrong_alias", "request_error"])
def test_local_model_health(
    monkeypatch: pytest.MonkeyPatch, broker_context: ProbeContext, mode: str
) -> None:
    def response(endpoint: str) -> dict[str, str]:
        if mode == "request_error":
            raise OSError("offline")
        alias = "local/model" if endpoint.endswith("local%2Fmodel") else "second"
        return {
            "status": "ok" if mode != "not_ready" else "loading",
            "model": "wrong" if mode == "wrong_alias" else alias,
        }

    request = Mock(side_effect=response)
    monkeypatch.setattr(probes, "_request_json", request)
    result = probes.llm_servers_are_ready(broker_context)
    assert result.passed is (mode == "ready"), result.message
    assert [call.args[0] for call in request.call_args_list] == [
        "/health/local%2Fmodel",
        "/health/second",
    ]


@pytest.mark.parametrize(
    "data,passed",
    [
        ([{"id": "local/model"}, {"id": "second"}, {"id": "online"}], True),
        ([{"id": "local/model"}, {"id": "second"}], False),
        ([], False),
        ({}, False),
        (["model"], False),
        ([{"id": ""}], False),
    ],
)
def test_advertised_models(
    monkeypatch: pytest.MonkeyPatch,
    broker_context: ProbeContext,
    data: object,
    passed: bool,
) -> None:
    monkeypatch.setattr(probes, "_request_json", lambda endpoint: {"data": data})
    assert probes.llm_models_are_available(broker_context).passed is passed


@pytest.mark.parametrize(
    "body,status,passed",
    [
        (b'{"data": []}', 200, True),
        (b"[]", 200, False),
        (b"bad json", 200, False),
        (b"{}", 503, False),
    ],
)
def test_http_response_validation_and_proxy_bypass(
    monkeypatch: pytest.MonkeyPatch, body: bytes, status: int, passed: bool
) -> None:
    response = MagicMock(status=status)
    response.__enter__.return_value = response
    response.read.return_value = body
    opener = Mock()
    opener.open.return_value = response
    build = Mock(return_value=opener)
    monkeypatch.setattr(probes.urllib.request, "build_opener", build)
    if passed:
        assert probes._request_json("/v1/models") == json.loads(body)
    else:
        with pytest.raises((ValueError, RuntimeError)):
            probes._request_json("/v1/models")
    assert build.call_args.args[0].proxies == {}
    assert (
        opener.open.call_args.args[0].full_url
        == "http://metisa-llm-broker:8000/v1/models"
    )
