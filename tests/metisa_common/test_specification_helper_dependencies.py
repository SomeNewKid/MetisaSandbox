from __future__ import annotations

import pytest

from metisa_common.models import SpecificationValidationError
from metisa_common.specification_helper import dependency_is_valid, parse_specification


@pytest.mark.parametrize(
    "dependency",
    [
        "requests==2.32.5",
        "requests>=2.32.5",
        "requests~=2.32.5",
        "arbitrary-package==1.2.3",
    ],
)
def test_dependency_is_valid_with_valid_dependency(dependency: str) -> None:
    assert dependency_is_valid(dependency)


@pytest.mark.parametrize(
    "dependency",
    [
        "",
        "   ",
        "requests",
        ">=1.15",
        "requests==",
        "requests>=",
        "requests~=",
        "requests==anything",
        "requests=1.15",
        "requests<1.15",
        "requests<=1.15",
        "requests!=1.15",
        "requests===1.15",
        "requests==1.15.*",
        "requests==1.15>=2.0",
        "invalid package==1.15",
    ],
)
def test_dependency_is_valid_with_invalid_dependency(dependency: str) -> None:
    assert not dependency_is_valid(dependency)


def test_missing_dependencies() -> None:
    toml = """
        agent_name = "sample_agent"
    """
    specification = parse_specification(toml)
    assert len(specification.dependencies) == 0


def test_not_iterable_dependencies() -> None:
    toml = """
        agent_name = "sample_agent"
        dependencies = "requests==2.32.5"
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


def test_empty_dependencies() -> None:
    toml = """
        agent_name = "sample_agent"
        dependencies = []
    """
    specification = parse_specification(toml)
    assert len(specification.dependencies) == 0


def test_dependencies_with_an_invalid_type() -> None:
    toml = """
        agent_name = "sample_agent"
        dependencies = [123]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


def test_dependencies_with_an_empty_value() -> None:
    toml = """
        agent_name = "sample_agent"
        dependencies = [""]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


def test_dependencies_with_a_whitespace_value() -> None:
    toml = """
        agent_name = "sample_agent"
        dependencies = ["   "]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


def test_dependencies_with_an_unpinned_version() -> None:
    toml = """
        agent_name = "sample_agent"
        dependencies = ["requests"]
    """
    with pytest.raises(SpecificationValidationError) as error:
        _ = parse_specification(toml)
    assert "unknown keys" not in str(error.value)


def test_valid_dependencies() -> None:
    toml = """
        agent_name = "sample_agent"
        dependencies = [
            "requests==2.32.5",
            "urllib3>=2.5.0",
            "playwright~=1.55.0",
        ]
    """
    specification = parse_specification(toml)
    assert specification.dependencies == frozenset(
        {
            "requests==2.32.5",
            "urllib3>=2.5.0",
            "playwright~=1.55.0",
        }
    )
