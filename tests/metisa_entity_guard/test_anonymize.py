from collections.abc import Iterator

import pytest
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NoOpNlpEngine

from metisa_entity_guard import _anonymize


@pytest.fixture
def model_free_analyzer(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    def _create_analyzer() -> AnalyzerEngine:
        nlp_engine = NoOpNlpEngine(
            models=[{"lang_code": "en", "model_name": ""}],
        )
        return AnalyzerEngine(nlp_engine=nlp_engine)

    _anonymize._get_analyzer.cache_clear()
    _anonymize._get_anonymizer_engine.cache_clear()

    monkeypatch.setattr(
        _anonymize,
        "AnalyzerEngine",
        _create_analyzer,
    )

    try:
        yield
    finally:
        _anonymize._get_analyzer.cache_clear()
        _anonymize._get_anonymizer_engine.cache_clear()


def test_anonymize_includes_coarse_numbers_by_default(
    model_free_analyzer: None,
) -> None:
    actual = _anonymize.anonymize("Reference: 12345678.")

    assert actual == "Reference: <COARSE_NUMBER>."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Reference: My phone number is 9332 1234.",
            "Reference: My phone number is <COARSE_NUMBER>.",
        ),
        (
            "Reference: My phone number is +61 9332 1234.",
            "Reference: My phone number is <COARSE_NUMBER>.",
        ),
        (
            "Reference: Our ABN is 50 110 219 460.",
            "Reference: Our ABN is <COARSE_NUMBER>.",
        ),
        (
            "Reference: Our ABN is 50110219460.",
            "Reference: Our ABN is <COARSE_NUMBER>.",
        ),
        (
            "Reference: My tax file number is 333-333-333.",
            "Reference: My tax file number is <COARSE_NUMBER>.",
        ),
        (
            "Reference: My tax file number is 333 333 333.",
            "Reference: My tax file number is <COARSE_NUMBER>.",
        ),
        (
            "Reference: My tax file number is 333333333.",
            "Reference: My tax file number is <COARSE_NUMBER>.",
        ),
        (
            "Reference: My Medicare number is 2428 77813 2.",
            "Reference: My Medicare number is <COARSE_NUMBER>.",
        ),
        (
            "Reference: My Medicare number is 2428778132.",
            "Reference: My Medicare number is <COARSE_NUMBER>.",
        ),
        (
            "Reference: My Medicare number is 2428778132 or similar.",
            "Reference: My Medicare number is <COARSE_NUMBER> or similar.",
        ),
        (
            "Reference: My Medicare number is 2428778132, I think.",
            "Reference: My Medicare number is <COARSE_NUMBER>, I think.",
        ),
        (
            "References: 12345678 and 87654321.",
            "References: <COARSE_NUMBER> and <COARSE_NUMBER>.",
        ),
        ("Reference: 1234567.", "Reference: 1234567."),
        ("Nothing sensitive here.", "Nothing sensitive here."),
        ("", ""),
        ("   ", "   "),
    ],
)
def test_anonymize_coarse_numbers(
    model_free_analyzer: None,
    text: str,
    expected: str,
) -> None:
    actual = _anonymize.anonymize(
        text,
        entities=["COARSE_NUMBER"],
    )

    assert actual == expected
