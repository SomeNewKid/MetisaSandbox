"""Tests parsing and validation of HAProxy backend declarations."""

from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import (
    HaproxyBackend,
    SpecificationValidationError,
)


def test_haproxy_missing_environs() -> None:
    """Handle omitted environment declarations using the table's defaults."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network","localnet"]

        [haproxy]
        backends = []
    """
    specification = parse_specification(toml)
    assert specification.haproxy is not None
    assert specification.haproxy.environs == frozenset()


def test_haproxy_empty_environs() -> None:
    """Accept an explicitly empty environment declaration array."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network","localnet"]

        [haproxy]
        backends = []
        environs = []
    """
    specification = parse_specification(toml)
    assert specification.haproxy is not None
    assert specification.haproxy.environs == frozenset()


def test_haproxy_valid_environs() -> None:
    """Preserve literals and references separately from workload environs."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network","localnet"]
        environs = ["SHARED=workload"]

        [haproxy]
        backends = []
        environs = [
            "SHARED=sidecar",
            "HOST_TOKEN=${host:HOST_SECRET}",
            "EMPTY=",
            "TOKEN=part1=part2",
        ]
    """
    specification = parse_specification(toml)
    assert specification.haproxy is not None
    assert specification.haproxy.environs == frozenset(
        {
            "SHARED=sidecar",
            "HOST_TOKEN=${host:HOST_SECRET}",
            "EMPTY=",
            "TOKEN=part1=part2",
        }
    )
    assert specification.environs == frozenset({"SHARED=workload"})


@pytest.mark.parametrize(
    "item",
    [
        "123",
        '""',
        '"   "',
        '"NAME"',
        '"1NAME=value"',
        '"PATH=value"',
        '"NAME=${vault:secret}"',
        '"NAME=${host:secret"',
    ],
)
def test_haproxy_environs_with_invalid_item(item: str) -> None:
    """Reject invalid declarations rather than rejecting the environs field."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network","localnet"]

        [haproxy]
        backends = []
        environs = ["VALID=value", {item}, "ALSO_VALID=value"]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "environs",
    ['"NAME=value"', '""', "123", "0", "true", "false", '{ NAME = "value" }', "{}"],
)
def test_haproxy_not_iterable_environs(environs: str) -> None:
    """Require environment declarations to be an array."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network","localnet"]

        [haproxy]
        backends = []
        environs = {environs}
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "environs",
    ['["NAME=value", "NAME=value"]', '["NAME=first", "NAME=second"]'],
    ids=["identical", "conflicting"],
)
def test_haproxy_environs_reject_duplicate_keys(environs: str) -> None:
    """Reject duplicate variable names within the table's declarations."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network","localnet"]

        [haproxy]
        backends = []
        environs = {environs}
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


def test_missing_haproxy() -> None:
    """Accept a specification without an HAProxy table."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "localnet"]
    """
    specification = parse_specification(toml)
    assert specification.haproxy is None


def test_haproxy_missing_details() -> None:
    """Treat an empty HAProxy table as absent."""
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
    """
    specification = parse_specification(toml)
    assert specification.haproxy is None


@pytest.mark.parametrize("key", ["unknown", "ports"])
def test_haproxy_unknown_key(key: str) -> None:
    """Reject unknown keys, including the obsolete ports field."""
    toml = f"""
        agent_name="sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        {key} = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_haproxy_invalid_if_localnet_capability_but_no_network_capability() -> None:
    """Require network capability when localnet capability is declared."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["localnet"]

        [haproxy]
        backends = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_haproxy_valid_if_no_localnet_capability() -> None:
    """Require localnet capability when the HAProxy table is configured."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network"]

        [haproxy]
        backends = []
    """
    specification = parse_specification(toml)
    assert specification.haproxy is not None


def test_haproxy_empty_backends() -> None:
    """Accept an explicitly empty backend array."""
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = []
    """
    specification = parse_specification(toml)
    assert specification.haproxy is not None
    assert specification.haproxy.backends == ()


def test_haproxy_populated_backends() -> None:
    """Hydrate an inline table into a backend object."""
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = [
            { listen_port = 3306, host = "host.docker.internal", port = 3306 },
        ]
    """
    specification = parse_specification(toml)
    assert specification.haproxy is not None
    assert specification.haproxy.backends == (
        HaproxyBackend(listen_port=3306, host="host.docker.internal", port=3306),
    )


def test_haproxy_multiple_backends() -> None:
    """Preserve backend order and distinct listener and destination ports."""
    toml = """
        agent_name="sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = [
            { listen_port = 13306, host = "host.docker.internal", port = 3306 },
            { listen_port = 1521, host = "172.16.1.2", port = 1521 },
        ]
    """
    specification = parse_specification(toml)
    assert specification.haproxy is not None
    assert specification.haproxy.backends == (
        HaproxyBackend(listen_port=13306, host="host.docker.internal", port=3306),
        HaproxyBackend(listen_port=1521, host="172.16.1.2", port=1521),
    )


def test_haproxy_duplicate_backends() -> None:
    """Reject identical backend declarations, including non-adjacent duplicates."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = [
            { listen_port = 3306, host = "host.docker.internal", port = 3306 },
            { listen_port = 1521, host = "172.16.1.2", port = 1521 },
            { listen_port = 3306, host = "host.docker.internal", port = 3306 },
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    ("host", "port"),
    [
        ("172.16.1.2", 3306),
        ("host.docker.internal", 3307),
        ("172.16.1.2", 1521),
    ],
)
def test_haproxy_conflicting_backends(host: str, port: int) -> None:
    """Reject a shared listener port with different destination hosts or ports."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = [
            {{ listen_port = 3306, host = "host.docker.internal", port = 3306 }},
            {{ listen_port = 3306, host = "{host}", port = {port} }},
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_haproxy_backends_as_array_of_tables() -> None:
    """Accept TOML array-of-tables syntax for backend objects."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network", "localnet"]

        [[haproxy.backends]]
        listen_port = 3306
        host = "host.docker.internal"
        port = 3306

        [[haproxy.backends]]
        listen_port = 1521
        host = "172.16.1.2"
        port = 1521
    """
    specification = parse_specification(toml)
    assert specification.haproxy is not None
    assert specification.haproxy.backends == (
        HaproxyBackend(listen_port=3306, host="host.docker.internal", port=3306),
        HaproxyBackend(listen_port=1521, host="172.16.1.2", port=1521),
    )


@pytest.mark.parametrize(
    "backends",
    ['"host.docker.internal:3306"', '""', "3306", "0", "true", "false", "{}"],
)
def test_haproxy_backends_must_be_an_array(backends: str) -> None:
    """Reject non-array backend declarations, including falsy values."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = {backends}
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    "backend", ['"host.docker.internal:3306"', "3306", "true", "[]"]
)
def test_haproxy_backends_must_contain_objects(backend: str) -> None:
    """Reject non-object items even after a valid backend."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = [
            {{ listen_port = 3306, host = "host.docker.internal", port = 3306 }},
            {backend},
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    "backend",
    [
        "{}",
        '{ host = "host.docker.internal", port = 3306 }',
        "{ listen_port = 3306, port = 3306 }",
        '{ listen_port = 3306, host = "host.docker.internal" }',
    ],
)
def test_haproxy_backend_missing_fields(backend: str) -> None:
    """Require listener port, host, and destination port in every backend."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = [{backend}]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize("field", ["listen_port", "port"])
@pytest.mark.parametrize("value", ['"3306"', "3306.5", "false", "[]", "{}"])
def test_haproxy_backend_invalid_port_types(field: str, value: str) -> None:
    """Reject invalid types for both port fields."""
    fields = {
        "listen_port": "3306",
        "host": '"host.docker.internal"',
        "port": "3306",
    }
    fields[field] = value
    backend = ", ".join(f"{name} = {item}" for name, item in fields.items())
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = [{{ {backend} }}]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize("field", ["listen_port", "port"])
@pytest.mark.parametrize("value", [0, -3306])
def test_haproxy_backend_non_positive_ports(field: str, value: int) -> None:
    """Reject zero and negative values for both port fields."""
    fields = {
        "listen_port": "3306",
        "host": '"host.docker.internal"',
        "port": "3306",
    }
    fields[field] = str(value)
    backend = ", ".join(f"{name} = {item}" for name, item in fields.items())
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = [{{ {backend} }}]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize("host", ['""', "123", "true", "false", "1.5", "[]", "{}"])
def test_haproxy_backend_invalid_host(host: str) -> None:
    """Reject empty hosts and non-string host values."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network", "localnet"]

        [haproxy]
        backends = [{{ listen_port = 3306, host = {host}, port = 3306 }}]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)
