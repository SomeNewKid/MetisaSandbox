"""Tests parsing and validation of LLM server model declarations."""

from __future__ import annotations

import json

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_common.specification_models import LlmModel, SpecificationValidationError


def test_llm_server_missing_details() -> None:
    """Treat an empty LLM server table as absent."""
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [llm_server]
    """
    specification = parse_specification(toml)
    assert specification.llm_server is None


def test_llm_server_unknown_key() -> None:
    """Reject unknown LLM server table keys."""
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [llm_server]
        unknown = []
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_llm_server_empty_models() -> None:
    """Accept an explicitly empty model array."""
    toml = """
        agent_name="sample_agent"
        capabilities = []

        [llm_server]
        models = []
    """
    specification = parse_specification(toml)
    assert specification.llm_server is not None
    assert specification.llm_server.models == ()


def test_llm_server_populated_models() -> None:
    """Hydrate an inline table into a model object, including its short alias."""
    toml = """
        agent_name = "sample_agent"
        capabilities = []

        [llm_server]
        models = [
            { alias = "granite", repo = "p/g", revision = "r1", filename = "g.gguf" },
        ]
    """
    specification = parse_specification(toml)
    assert specification.llm_server is not None
    assert specification.llm_server.models == (
        LlmModel(alias="granite", repo="p/g", revision="r1", filename="g.gguf"),
    )


def test_llm_server_multiple_models() -> None:
    """Preserve the order and fields of models with distinct aliases."""
    toml = """
        agent_name = "sample_agent"
        capabilities = []

        [llm_server]
        models = [
            { alias = "granite", repo = "p/g", revision = "r1", filename = "g.gguf" },
            { alias = "qwen", repo = "p/q", revision = "r2", filename = "q.gguf" },
        ]
    """
    specification = parse_specification(toml)
    assert specification.llm_server is not None
    assert specification.llm_server.models == (
        LlmModel(alias="granite", repo="p/g", revision="r1", filename="g.gguf"),
        LlmModel(alias="qwen", repo="p/q", revision="r2", filename="q.gguf"),
    )


def test_llm_server_duplicate_models() -> None:
    """Reject identical model declarations, including non-adjacent duplicates."""
    toml = """
        agent_name = "sample_agent"
        capabilities = []

        [llm_server]
        models = [
            { alias = "granite", repo = "p/g", revision = "r1", filename = "g.gguf" },
            { alias = "qwen", repo = "p/q", revision = "r2", filename = "q.gguf" },
            { alias = "granite", repo = "p/g", revision = "r1", filename = "g.gguf" },
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_llm_server_duplicate_aliases() -> None:
    """Reject shared aliases even when the model artifacts differ."""
    toml = """
        agent_name = "sample_agent"
        capabilities = []

        [llm_server]
        models = [
            { alias = "granite", repo = "p/g", revision = "r1", filename = "g.gguf" },
            { alias = "qwen", repo = "p/q", revision = "r2", filename = "q.gguf" },
            { alias = "granite", repo = "p/x", revision = "r3", filename = "x.gguf" },
        ]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_llm_server_models_as_array_of_tables() -> None:
    """Accept TOML array-of-tables syntax for model objects with aliases."""
    toml = """
        agent_name = "sample_agent"
        capabilities = []

        [[llm_server.models]]
        alias = "granite"
        repo = "p/g"
        revision = "r1"
        filename = "g.gguf"

        [[llm_server.models]]
        alias = "qwen"
        repo = "p/q"
        revision = "r2"
        filename = "q.gguf"
    """
    specification = parse_specification(toml)
    assert specification.llm_server is not None
    assert specification.llm_server.models == (
        LlmModel(alias="granite", repo="p/g", revision="r1", filename="g.gguf"),
        LlmModel(alias="qwen", repo="p/q", revision="r2", filename="q.gguf"),
    )


@pytest.mark.parametrize("models", ['"model"', '""', "123", "0", "true", "false", "{}"])
def test_llm_server_models_must_be_an_array(models: str) -> None:
    """Reject non-array model declarations, including falsy values."""
    toml = f"""
        agent_name = "sample_agent"
        capabilities = []

        [llm_server]
        models = {models}
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize("model", ['"qwen3:4b"', '""', "123", "true", "false", "[]"])
def test_llm_server_models_must_contain_objects(model: str) -> None:
    """Reject non-object items even after a valid model."""
    valid_model = _model_definition()
    toml = f"""
        agent_name = "sample_agent"
        capabilities = []

        [llm_server]
        models = [{{ {valid_model} }}, {model}]
    """
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize("field", ["alias", "repo", "revision", "filename"])
def test_llm_server_model_missing_fields(field: str) -> None:
    """Require alias, repo, revision, and filename in every model."""
    fields = _model_fields()
    del fields[field]
    model = ", ".join(f"{name} = {item}" for name, item in fields.items())
    toml = _model_specification(model)
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def test_llm_server_model_empty_object() -> None:
    """Reject a model object without any fields."""
    toml = _model_specification("")
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize("field", ["alias", "repo", "revision", "filename"])
@pytest.mark.parametrize(
    "value", ['""', "123", "0", "1.5", "true", "false", "[]", "{}"]
)
def test_llm_server_model_invalid_fields(field: str, value: str) -> None:
    """Reject empty strings and non-string values for each model field."""
    model = _model_definition(field, value)
    toml = _model_specification(model)
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


@pytest.mark.parametrize(
    "alias", ["granite", "qwen-3", "g", "1", "3b", "g--q4", "a" * 52]
)
def test_llm_server_model_valid_alias(alias: str) -> None:
    """Accept lowercase DNS labels up to 63 characters including the prefix."""
    model = _model_definition("alias", json.dumps(alias))
    toml = _model_specification(model)
    specification = parse_specification(toml)
    assert specification.llm_server is not None
    assert specification.llm_server.models == (
        LlmModel(alias=alias, repo="p/g", revision="r1", filename="g.gguf"),
    )


@pytest.mark.parametrize(
    "alias",
    [
        " ",
        "   ",
        "\t",
        "\n",
        " granite",
        "granite ",
        "gran ite",
        "gran\tite",
        "gran\nite",
        "Granite",
        "GRANITE",
        "-granite",
        "granite-",
        "-",
        "granite_q4",
        "granite.q4",
        "granite/q4",
        "granite\\q4",
        "granite:q4",
        "granite@q4",
        "granite#q4",
        "granite?q4",
        "granite*q4",
        "granite+q4",
        "granite%q4",
        "granite=q4",
        "granite,q4",
        "granit\u00e9",
        "a" * 53,
    ],
)
def test_llm_server_model_invalid_alias(alias: str) -> None:
    """Reject whitespace, invalid label characters, and excessive alias length."""
    model = _model_definition("alias", json.dumps(alias))
    toml = _model_specification(model)
    with pytest.raises(SpecificationValidationError):
        _ = parse_specification(toml)


def _model_fields() -> dict[str, str]:
    return {
        "alias": '"granite"',
        "repo": '"p/g"',
        "revision": '"r1"',
        "filename": '"g.gguf"',
    }


def _model_definition(field: str = "alias", value: str = '"granite"') -> str:
    fields = _model_fields()
    fields[field] = value
    return ", ".join(f"{name} = {item}" for name, item in fields.items())


def _model_specification(model: str) -> str:
    return f"""
        agent_name = "sample_agent"
        capabilities = []

        [llm_server]
        models = [{{ {model} }}]
    """
