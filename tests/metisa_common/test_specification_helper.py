from __future__ import annotations

import re

import pytest

from metisa_common.models import SpecificationValidationError
from metisa_common.specification_helper import get_image_tag, parse_specification


def test_empty_toml_file() -> None:
    toml = ""
    with pytest.raises(ValueError):
        _ = parse_specification(toml)


def test_missing_agent_name() -> None:
    toml = """
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_invalid_type_agent_name() -> None:
    toml = """
        agent_name = 123
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_empty_agent_name() -> None:
    toml = """
        agent_name = ""
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_whitespace_agent_name() -> None:
    toml = """
        agent_name = "  "
        capabilities = [
            "network",
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_minimal_toml_file() -> None:
    toml = """
        agent_name="sample_agent"
    """
    specification = parse_specification(toml)
    assert specification.agent_name == "sample_agent"


def test_minimal_toml_file_with_whitespaced_value() -> None:
    toml = """
        agent_name="  sample_agent  "
    """
    specification = parse_specification(toml)
    assert specification.agent_name == "sample_agent"


def test_image_tag_with_only_agent_name() -> None:
    toml = """
        agent_name = "sample_agent"
    """
    image_tag = _get_image_tag_from_toml(toml)
    _assert_valid_image_tag(image_tag)


def test_image_tag_with_capabilities_and_no_dependencies() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "interactive",
            "network",
        ]
    """
    image_tag = _get_image_tag_from_toml(toml)
    _assert_valid_image_tag(image_tag)


def test_image_tag_with_dependencies_and_no_capabilities() -> None:
    toml = """
        agent_name = "sample_agent"
        dependencies = [
            "requests==2.34.2",
            "urllib3>=2.5.0",
        ]
    """
    image_tag = _get_image_tag_from_toml(toml)
    _assert_valid_image_tag(image_tag)


def test_image_tag_with_capabilities_and_dependencies() -> None:
    toml = """
        agent_name = "sample_agent"
        capabilities = [
            "interactive",
            "network",
        ]
        dependencies = [
            "requests==2.34.2",
            "urllib3>=2.5.0",
        ]
    """
    image_tag = _get_image_tag_from_toml(toml)
    _assert_valid_image_tag(image_tag)


def test_capability_order_does_not_change_image_tag() -> None:
    first_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "interactive",
            "network",
        ]
    """
    second_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network",
            "interactive",
        ]
    """
    first_image_tag = _get_image_tag_from_toml(first_toml)
    second_image_tag = _get_image_tag_from_toml(second_toml)
    assert first_image_tag == second_image_tag


def test_dependency_order_does_not_change_image_tag() -> None:
    first_toml = """
        agent_name = "sample_agent"
        dependencies = [
            "requests==2.34.2",
            "urllib3>=2.5.0",
        ]
    """
    second_toml = """
        agent_name = "sample_agent"
        dependencies = [
            "urllib3>=2.5.0",
            "requests==2.34.2",
        ]
    """
    first_image_tag = _get_image_tag_from_toml(first_toml)
    second_image_tag = _get_image_tag_from_toml(second_toml)
    assert first_image_tag == second_image_tag


def test_collection_order_does_not_change_image_tag() -> None:
    first_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "interactive",
            "network",
        ]
        dependencies = [
            "requests==2.34.2",
            "urllib3>=2.5.0",
        ]
    """
    second_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network",
            "interactive",
        ]
        dependencies = [
            "urllib3>=2.5.0",
            "requests==2.34.2",
        ]
    """
    first_image_tag = _get_image_tag_from_toml(first_toml)
    second_image_tag = _get_image_tag_from_toml(second_toml)
    assert first_image_tag == second_image_tag


def test_unrelated_tables_do_not_change_image_tag() -> None:
    squid_proxy_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "interactive",
            "network",
        ]
        dependencies = [
            "requests==2.34.2",
            "urllib3>=2.5.0",
        ]

        [squid_proxy]
        allowed_domains = [
            ".example.com",
        ]
    """
    haproxy_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network",
            "interactive",
        ]
        dependencies = [
            "urllib3>=2.5.0",
            "requests==2.34.2",
        ]

        [haproxy]
        ports = [
            3306,
        ]
    """
    squid_image_tag = _get_image_tag_from_toml(squid_proxy_toml)
    haproxy_image_tag = _get_image_tag_from_toml(haproxy_toml)
    assert squid_image_tag == haproxy_image_tag


def test_different_dependencies_produce_different_image_tags() -> None:
    first_toml = """
        agent_name = "sample_agent"
        dependencies = [
            "requests==2.34.2",
        ]
    """
    second_toml = """
        agent_name = "sample_agent"
        dependencies = [
            "urllib3>=2.5.0",
        ]
    """
    first_image_tag = _get_image_tag_from_toml(first_toml)
    second_image_tag = _get_image_tag_from_toml(second_toml)
    assert first_image_tag != second_image_tag


def test_different_capabilities_produce_different_image_tags() -> None:
    first_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "interactive",
        ]
    """
    second_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network",
        ]
    """
    first_image_tag = _get_image_tag_from_toml(first_toml)
    second_image_tag = _get_image_tag_from_toml(second_toml)
    assert first_image_tag != second_image_tag


def test_same_capabilities_and_different_dependencies_produce_different_tags() -> None:
    first_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network",
        ]
        dependencies = [
            "requests==2.34.2",
        ]
    """
    second_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network",
        ]
        dependencies = [
            "urllib3>=2.5.0",
        ]
    """
    first_image_tag = _get_image_tag_from_toml(first_toml)
    second_image_tag = _get_image_tag_from_toml(second_toml)
    assert first_image_tag != second_image_tag


def test_different_capabilities_and_dependencies_produce_different_tags() -> None:
    first_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "interactive",
        ]
        dependencies = [
            "requests==2.34.2",
        ]
    """
    second_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network",
        ]
        dependencies = [
            "urllib3>=2.5.0",
        ]
    """
    first_image_tag = _get_image_tag_from_toml(first_toml)
    second_image_tag = _get_image_tag_from_toml(second_toml)
    assert first_image_tag != second_image_tag


def test_different_dependency_versions_produce_different_image_tags() -> None:
    first_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network",
        ]
        dependencies = [
            "requests==2.34.1",
        ]
    """
    second_toml = """
        agent_name = "sample_agent"
        capabilities = [
            "network",
        ]
        dependencies = [
            "requests==2.34.2",
        ]
    """
    first_image_tag = _get_image_tag_from_toml(first_toml)
    second_image_tag = _get_image_tag_from_toml(second_toml)
    assert first_image_tag != second_image_tag


def _get_image_tag_from_toml(toml: str) -> str:
    specification = parse_specification(toml)
    return get_image_tag(specification)


def _assert_valid_image_tag(image_tag: str) -> None:
    assert re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", image_tag)
