"""Tests parsing and validation of workload environment declarations."""

from __future__ import annotations

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
            "LITERAL=prefix-${host:NAME}",
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
            "LITERAL=prefix-${host:NAME}",
        }
    )
