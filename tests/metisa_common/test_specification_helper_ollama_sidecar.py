from __future__ import annotations

import pytest

from metisa_common.models import SpecificationValidationError
from metisa_common.specification_helper import parse_specification


def test_ollama_sidecar_missing_details() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [ollama_sidecar]
    """
    specification = parse_specification(toml)
    assert specification.ollama_sidecar is None


def test_ollama_sidecar_unknown_key() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [ollama_sidecar]
        unknown = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_ollama_sidecar_empty_models() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [ollama_sidecar]
        models = []
    """
    specification = parse_specification(toml)
    assert specification.ollama_sidecar is not None
    assert len(specification.ollama_sidecar.models) == 0


def test_ollama_sidecar_populated_models() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [ollama_sidecar]
        models = [
            "qwen3:4b"
        ]
    """
    specification = parse_specification(toml)
    assert specification.ollama_sidecar is not None
    assert len(specification.ollama_sidecar.models) == 1
    assert specification.ollama_sidecar.models[0] == "qwen3:4b"


def test_ollama_sidecar_invalid_types_in_models() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [ollama_sidecar]
        models = [
            3306
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_ollama_sidecar_invalid_value_in_models() -> None:
    toml = """
        schema_version = 1
        workload_name="sample_agent"
        capabilities = []

        [ollama_sidecar]
        models = [
            ""
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)
