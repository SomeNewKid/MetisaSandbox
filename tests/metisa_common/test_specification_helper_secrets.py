"""Test secret declarations at workload and supported sidecar scopes."""

from __future__ import annotations

import json

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import (
    MetisaSpecification,
    SpecificationValidationError,
)


@pytest.fixture(params=["workload", "mcp_server", "llm_broker"])
def secret_scope(request: pytest.FixtureRequest) -> str:
    """Exercise every specification scope that supports secret declarations."""
    return str(request.param)


def test_missing_secrets(secret_scope: str) -> None:
    """Default missing secrets to an empty collection in each scope."""
    toml = _create_toml(secret_scope)
    specification = parse_specification(toml)
    secrets = _get_secrets(specification, secret_scope)
    assert secrets == frozenset()


def test_empty_secrets(secret_scope: str) -> None:
    """Accept an explicitly empty secrets array in each scope."""
    toml = _create_toml(secret_scope, "[]")
    specification = parse_specification(toml)
    secrets = _get_secrets(specification, secret_scope)
    assert secrets == frozenset()


def test_valid_secrets(secret_scope: str) -> None:
    """Preserve literal values and host references without resolving them."""
    declarations = [
        "TOKEN=hard-coded value",
        "HOST_TOKEN=${host:HOST_SECRET}",
        "EMPTY=",
        "PADDED= leading and trailing spaces ",
        "COMPOSITE=part1=part2",
        "URL=https://example.com:443/path",
        "LITERAL={host:NAME}",
        "PREFIXED_LITERAL=prefix-${host:NAME}",
        "_PRIVATE=value",
        "mixed_Case123=value",
    ]
    raw_secrets = json.dumps(declarations)
    toml = _create_toml(secret_scope, raw_secrets)
    specification = parse_specification(toml)
    secrets = _get_secrets(specification, secret_scope)
    assert secrets == frozenset(declarations)


@pytest.mark.parametrize(
    "raw_secrets",
    [
        '"NAME=value"',
        '""',
        "123",
        "0",
        "true",
        "false",
        '{ NAME = "value" }',
        "{}",
    ],
)
def test_secrets_require_an_array(secret_scope: str, raw_secrets: str) -> None:
    """Reject a non-array secrets field rather than an unknown field."""
    toml = _create_toml(secret_scope, raw_secrets)
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize("item", ["123", "true", "[]", "{}"])
def test_secrets_reject_non_string_items(secret_scope: str, item: str) -> None:
    """Reject non-string items even when preceded by a valid assignment."""
    raw_secrets = f'["VALID=value", {item}]'
    toml = _create_toml(secret_scope, raw_secrets)
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "1NAME",
        " NAME",
        "NAME ",
        "NA ME",
        "\tNAME",
        "NAME\n",
        "NAME-WITH-DASH",
        "NAME.WITH.DOT",
        "NAME:SUFFIX",
        "NAME/PATH",
        "$NAME",
        "NAME!",
        "\u00c9NAME",
        "NAM\u00c9",
        "NAME\u0661",
    ],
)
def test_secrets_reject_invalid_names(secret_scope: str, name: str) -> None:
    """Apply the ASCII variable-name pattern to secret names in every scope."""
    raw_secrets = json.dumps([f"{name}=value"])
    toml = _create_toml(secret_scope, raw_secrets)
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "declaration",
    [
        "",
        "   ",
        "NAME",
        "NAME=before\x00after",
        "NAME=${vault:secret}",
        "NAME=${HOST:secret}",
        "NAME=${host:secret",
        "NAME=${host:secret}suffix",
        "NAME=${host}",
        "NAME=${host,secret}",
        "NAME=${host:secret:extra}",
        "NAME=${host::secret}",
        "NAME=${host:}",
    ],
)
def test_secrets_reject_invalid_declarations(
    secret_scope: str, declaration: str
) -> None:
    """Validate secret assignments without accepting malformed host references."""
    raw_secrets = json.dumps(["VALID=value", declaration])
    toml = _create_toml(secret_scope, raw_secrets)
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "declarations",
    [
        ["NAME=value", "NAME=value"],
        ["NAME=first", "NAME=second"],
        ["NAME=first", "OTHER=value", "NAME=second"],
        ["NAME=literal", "NAME=${host:HOST_NAME}"],
        ["NAME=", "NAME=value"],
    ],
    ids=["identical", "conflicting", "non-adjacent", "host-reference", "empty-value"],
)
def test_secrets_reject_duplicate_keys(
    secret_scope: str, declarations: list[str]
) -> None:
    """Reject repeated secret names regardless of their assignment values."""
    raw_secrets = json.dumps(declarations)
    toml = _create_toml(secret_scope, raw_secrets)
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "name",
    [
        "METISA_RUNTIME_ROLE",
        "SANDBOX_OUTPUT_DIR",
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "NO_PROXY",
        "LD_PRELOAD",
        "LD_METISA_POLICY_PROBE",
        "PATH",
        "PYTHONPATH",
        "PYTHON_METISA_POLICY_PROBE",
        "HOME",
        "XDG_CONFIG_HOME",
        "TMPDIR",
        "SSH_AUTH_SOCK",
        "DISPLAY",
    ],
)
@pytest.mark.parametrize("value", ["literal", "${host:HOST_SECRET}"])
def test_secrets_accept_names_reserved_for_environs(
    secret_scope: str, name: str, value: str
) -> None:
    """Allow reserved environment names as secret keys for either value form."""
    declaration = f"{name}={value}"
    raw_secrets = json.dumps([declaration])
    toml = _create_toml(secret_scope, raw_secrets)
    specification = parse_specification(toml)
    secrets = _get_secrets(specification, secret_scope)
    assert secrets == frozenset({declaration})


def test_secrets_and_environs_have_independent_keys(secret_scope: str) -> None:
    """Keep secrets separate from environs even when their names coincide."""
    toml = _create_toml(secret_scope, '["SHARED=secret"]')
    specification = parse_specification(toml)
    secrets = _get_secrets(specification, secret_scope)
    assert secrets == frozenset({"SHARED=secret"})
    if secret_scope == "workload":
        assert specification.environs == frozenset({"SHARED=public"})
    elif secret_scope == "mcp_server":
        assert specification.mcp_server is not None
        assert specification.mcp_server.environs == frozenset({"SHARED=public"})
        assert specification.secrets == frozenset()
    else:
        assert specification.llm_broker is not None
        assert specification.llm_broker.environs == frozenset({"SHARED=public"})
        assert specification.secrets == frozenset()


def _create_toml(secret_scope: str, raw_secrets: str | None = None) -> str:
    toml = 'agent_name = "sample_agent"\n'
    if secret_scope != "workload":
        toml += f"[{secret_scope}]\n"
    # Keep sidecar tables nonempty so missing secrets exercise their defaults.
    toml += 'environs = ["SHARED=public"]\n'
    if raw_secrets is not None:
        toml += f"secrets = {raw_secrets}\n"
    return toml


def _get_secrets(
    specification: MetisaSpecification, secret_scope: str
) -> frozenset[str]:
    if secret_scope == "workload":
        return specification.secrets
    if secret_scope == "mcp_server":
        assert specification.mcp_server is not None
        return specification.mcp_server.secrets
    assert secret_scope == "llm_broker"
    assert specification.llm_broker is not None
    return specification.llm_broker.secrets
