"""Test parsing and validation of playwright_chromium environment declarations."""

from __future__ import annotations

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import SpecificationValidationError


def test_playwright_chromium_invalid_if_no_network_capability() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "mcp_server", "prompt_guard", "entity_guard", "playwright_chromium",
        ]

        [playwright_chromium]
        environs = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_playwright_chromium_missing_environs() -> None:
    """Handle omitted environment declarations using the table's defaults."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network","playwright_chromium"]

        [playwright_chromium]
    """
    specification = parse_specification(toml)
    assert specification.playwright_chromium is None


def test_playwright_chromium_empty_environs() -> None:
    """Accept an explicitly empty environment declaration array."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network","playwright_chromium"]

        [playwright_chromium]
        environs = []
    """
    specification = parse_specification(toml)
    assert specification.playwright_chromium is not None
    assert specification.playwright_chromium.environs == frozenset()


def test_playwright_chromium_valid_environs() -> None:
    """Preserve literals and references separately from workload environs."""
    toml = """
        agent_name = "sample_agent"
        capabilities = ["network","playwright_chromium"]
        environs = ["SHARED=workload"]

        [playwright_chromium]
        environs = [
            "SHARED=sidecar",
            "HOST_TOKEN=${host:HOST_SECRET}",
            "EMPTY=",
            "TOKEN=part1=part2",
        ]
    """
    specification = parse_specification(toml)
    assert specification.playwright_chromium is not None
    assert specification.playwright_chromium.environs == frozenset(
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
def test_playwright_chromium_environs_with_invalid_item(item: str) -> None:
    """Reject invalid declarations rather than rejecting the environs field."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network","playwright_chromium"]

        [playwright_chromium]
        environs = ["VALID=value", {item}, "ALSO_VALID=value"]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


@pytest.mark.parametrize(
    "environs",
    ['"NAME=value"', '""', "123", "0", "true", "false", '{ NAME = "value" }', "{}"],
)
def test_playwright_chromium_not_iterable_environs(environs: str) -> None:
    """Require environment declarations to be an array."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network","playwright_chromium"]

        [playwright_chromium]
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
def test_playwright_chromium_environs_reject_duplicate_keys(environs: str) -> None:
    """Reject duplicate variable names within the table's declarations."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = ["network","playwright_chromium"]

        [playwright_chromium]
        environs = {environs}
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)
