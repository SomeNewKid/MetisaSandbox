"""Tests parsing and validation of workload environment declarations."""

from __future__ import annotations

import json

import pytest

from metisa_common.specification_helper import environ_is_valid, parse_specification
from metisa_common.specification_models import SpecificationValidationError


@pytest.mark.parametrize(
    "environ",
    [
        "METISA_PROBE_1=hard-coded value",
        "METISA_PROBE_2=${host:METISA_PROBE_2}",
        "SECRET=${host:HOST_SECRET}",
        "EMPTY=",
        "TOKEN=part1=part2",
        "URL=https://example.com:443/path",
        "LITERAL={host:NAME}",
        "LITERAL=prefix-${host:NAME}",
    ],
)
def test_environ_is_valid_with_valid_environ(environ: str) -> None:
    """Accept literals and whole-value host references."""
    assert environ_is_valid(environ)


@pytest.mark.parametrize(
    "environ",
    [
        "",
        "   ",
        "NAME",
        "=value",
        "NAME=${vault:secret}",
        "NAME=${unsupported:secret}",
        "NAME=${HOST:secret}",
        "NAME=${host:secret",
        "NAME=${host:secret}suffix",
        "NAME=${host}",
        "NAME=${host,secret}",
        "NAME=${host:secret:extra}",
        "NAME=${host::secret}",
    ],
)
def test_environ_is_valid_with_invalid_environ(environ: str) -> None:
    """Reject missing pairs and unsupported or malformed resolver references."""
    assert not environ_is_valid(environ)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "1NAME",
        "123",
        " NAME",
        "NAME ",
        "NA ME",
        "\tNAME",
        "NAME\t",
        "NAME\n",
        "NAME\r",
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
def test_environs_reject_invalid_names(name: str) -> None:
    """Reject names outside the ASCII pattern [A-Za-z_][A-Za-z0-9_]*."""
    declaration = json.dumps(f"{name}=value")
    toml = f"""
        agent_name = "sample_agent"
        environs = [{declaration}]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_missing_environs() -> None:
    """Default missing declarations to an empty collection."""
    toml = """
        agent_name = "sample_agent"
    """
    specification = parse_specification(toml)
    assert specification.environs == frozenset()


@pytest.mark.parametrize(
    "environs",
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
def test_not_iterable_environs(environs: str) -> None:
    """Require the declarations field to be an array."""
    toml = f"""
        agent_name = "sample_agent"
        environs = {environs}
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


def test_empty_environs() -> None:
    """Accept an explicitly empty array."""
    toml = """
        agent_name = "sample_agent"
        environs = []
    """
    specification = parse_specification(toml)
    assert specification.environs == frozenset()


@pytest.mark.parametrize(
    "environs",
    [
        ["NAME=value", "NAME=value"],
        ["NAME=first", "NAME=second"],
        ["NAME=first", "OTHER=value", "NAME=second"],
        ["NAME=literal", "NAME=${host:HOST_NAME}"],
        ["NAME=", "NAME=value"],
    ],
    ids=["identical", "conflicting", "non-adjacent", "host-reference", "empty-value"],
)
def test_environs_reject_duplicate_keys(environs: list[str]) -> None:
    """Reject repeated variable names regardless of their assignment values."""
    declarations = json.dumps(environs)
    toml = f"""
        agent_name = "sample_agent"
        environs = {declarations}
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize("item", ["123", "true", "[]", "{}"])
def test_environs_with_an_invalid_type(item: str) -> None:
    """Reject non-string items even when valid strings precede them."""
    toml = f"""
        agent_name = "sample_agent"
        environs = ["NAME=value", {item}]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


def test_environs_reject_null_character_in_value() -> None:
    """Reject a NUL character decoded from a valid TOML string escape."""
    declaration = json.dumps("NAME=before\x00after")
    toml = f"""
        agent_name = "sample_agent"
        environs = [{declaration}]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_environs_with_an_empty_value() -> None:
    """Reject an empty array item rather than an empty assignment value."""
    toml = """
        agent_name = "sample_agent"
        environs = [""]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


def test_environs_with_a_whitespace_value() -> None:
    """Reject an array item containing only whitespace."""
    toml = """
        agent_name = "sample_agent"
        environs = ["   "]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "environ",
    [
        "NAME",
        "=value",
        "NAME=${vault:secret}",
        "NAME=${unsupported:secret}",
        "NAME=${HOST:secret}",
        "NAME=${host:secret",
        "NAME=${host:secret}suffix",
        "NAME=${host}",
        "NAME=${host,secret}",
        "NAME=${host:secret:extra}",
        "NAME=${host::secret}",
    ],
)
def test_environs_with_an_invalid_value(environ: str) -> None:
    """Report invalid declarations as specification validation errors."""
    toml = f"""
        agent_name = "sample_agent"
        environs = ["VALID=value", "{environ}"]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize("name", ["METISA_RUNTIME_ROLE", "SANDBOX_OUTPUT_DIR"])
def test_environs_reject_internal_variables(name: str) -> None:
    """Reject declarations that override sandbox startup configuration."""
    toml = f"""
        agent_name = "sample_agent"
        environs = ["{name}=value"]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    "name",
    [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    ],
)
def test_environs_reject_proxy_variables(name: str) -> None:
    """Reject declarations that override managed proxy configuration."""
    toml = f"""
        agent_name = "sample_agent"
        environs = ["{name}=value"]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    "name",
    [
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "LD_AUDIT",
        "LD_DEBUG",
        "LD_DEBUG_OUTPUT",
        "LD_BIND_NOW",
        "LD_BIND_NOT",
        "LD_DYNAMIC_WEAK",
        "LD_HWCAP_MASK",
        "LD_ORIGIN_PATH",
        "LD_PROFILE",
        "LD_PROFILE_OUTPUT",
        "LD_SHOW_AUXV",
        "LD_USE_LOAD_BIAS",
        "LD_METISA_POLICY_PROBE",
    ],
)
def test_environs_reject_dynamic_loader_variables(name: str) -> None:
    """Reject dynamic-loader variables, including unrecognized LD_ names."""
    toml = f"""
        agent_name = "sample_agent"
        environs = ["{name}=value"]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    "name",
    [
        "PATH",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
        "PYTHONUSERBASE",
        "PYTHONNOUSERSITE",
        "PYTHONSAFEPATH",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONPYCACHEPREFIX",
        "PYTHONWARNINGS",
        "PYTHONOPTIMIZE",
        "PYTHONHASHSEED",
        "PYTHONIOENCODING",
        "PYTHONUNBUFFERED",
        "PYTHON_METISA_POLICY_PROBE",
    ],
)
def test_environs_reject_execution_configuration_variables(name: str) -> None:
    """Reject executable lookup and Python-prefixed configuration variables."""
    toml = f"""
        agent_name = "sample_agent"
        environs = ["{name}=value"]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    "name",
    [
        "HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_RUNTIME_DIR",
        "GNUPGHOME",
        "TMPDIR",
        "TMP",
        "TEMP",
    ],
)
def test_environs_reject_storage_location_variables(name: str) -> None:
    """Reject declarations that redirect configuration or temporary storage."""
    toml = f"""
        agent_name = "sample_agent"
        environs = ["{name}=value"]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    "name",
    [
        "SSH_AUTH_SOCK",
        "GPG_AGENT_INFO",
        "DBUS_SESSION_BUS_ADDRESS",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
    ],
)
def test_environs_reject_host_channel_variables(name: str) -> None:
    """Reject declarations that configure host integration channels."""
    toml = f"""
        agent_name = "sample_agent"
        environs = ["{name}=value"]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_valid_environs() -> None:
    """Preserve literal assignments and unresolved host references."""
    toml = """
        agent_name = "sample_agent"
        environs = [
            "METISA_PROBE_1=hard-coded value",
            "METISA_PROBE_2=${host:METISA_PROBE_2}",
            "SECRET=${host:HOST_SECRET}",
            "EMPTY=",
            "TOKEN=part1=part2",
            "URL=https://example.com:443/path",
            "LITERAL={host:NAME}",
            "PREFIXED_LITERAL=prefix-${host:NAME}",
        ]
    """
    specification = parse_specification(toml)
    assert specification.environs == frozenset(
        {
            "METISA_PROBE_1=hard-coded value",
            "METISA_PROBE_2=${host:METISA_PROBE_2}",
            "SECRET=${host:HOST_SECRET}",
            "EMPTY=",
            "TOKEN=part1=part2",
            "URL=https://example.com:443/path",
            "LITERAL={host:NAME}",
            "PREFIXED_LITERAL=prefix-${host:NAME}",
        }
    )
