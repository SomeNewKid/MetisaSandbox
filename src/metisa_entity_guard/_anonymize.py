"""Performs anonymization of text."""

from __future__ import annotations

from functools import cache
from threading import Lock

from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
    RecognizerResult,
)
from presidio_analyzer.predefined_recognizers import PhoneRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_anonymizer.entities import RecognizerResult as AnonymizerRecognizerResult

_ANALYZER_LOCK = Lock()
_ANONYMIZER_LOCK = Lock()


def anonymize(
    text: str,
    entities: list[str] | None = None,
) -> str:
    """Return the original text with entities redacted."""
    if not text.strip():
        return text

    if entities is None:
        entities = [
            "CREDIT_CARD",
            "EMAIL_ADDRESS",
            "IBAN_CODE",  # International Bank Account Number (IBAN)
            "PERSON",  # A full person name
            "PHONE_NUMBER",
            "AU_ABN",  # Australian Business Number (ABN)
            "AU_ACN",  # Australian Company Number (ACN)
            "AU_TFN",  # Tax file number (TFN)
            "AU_MEDICARE",  # Medicare number
            "COARSE_NUMBER",
        ]

    with _ANALYZER_LOCK:
        analyzer = _get_analyzer()

        analyzer_results: list[RecognizerResult] = analyzer.analyze(
            text=text,
            entities=entities,
            language="en",
        )

    anonymizer_results = [
        AnonymizerRecognizerResult(
            entity_type=result.entity_type,
            start=result.start,
            end=result.end,
            score=result.score,
        )
        for result in analyzer_results
    ]

    with _ANONYMIZER_LOCK:
        operators = {
            "COARSE_NUMBER": OperatorConfig("replace", {"new_value": "<COARSE_NUMBER>"})
        }

        anonymizer = _get_anonymizer_engine()

        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=anonymizer_results,
            operators=operators,
        )

    return anonymized.text


def initialize_anonymizer_engine() -> None:
    """Initialize the anonymizer engine by caching it."""
    with _ANALYZER_LOCK:
        _ = _get_analyzer()
    with _ANONYMIZER_LOCK:
        _ = _get_anonymizer_engine()


# This is a purposely coarse number recognizer,
# created as an exercise in learning how to extend
# the Presidio library.
def _create_coarse_number_recognizer() -> PatternRecognizer:
    regex = (
        r"(?<!\w)"  # Do not start immediately after a word character
        r"\+?"  # Allow an optional leading '+' character
        "[0-9]"  # Match the first digit
        "(?:[ -]?[0-9]){7,}"  # At least seven more digits, maybe with space or hyphen
        r"(?!\w)"  # Do not end immediately before a word character
    )

    pattern = Pattern(
        name="coarse_number_recognizer",
        regex=regex,
        score=0.7,
    )

    return PatternRecognizer(
        name="CoarseNumberRecognizer",
        supported_entity="COARSE_NUMBER",
        supported_language="en",
        patterns=[pattern],
    )


@cache
def _get_analyzer() -> AnalyzerEngine:
    # Sets up the engine and loads the NLP module (spaCy)
    # and any PII recognizers.
    analyzer = AnalyzerEngine()

    phone_recognizer = PhoneRecognizer(
        supported_regions=["AU"],
        supported_entity="PHONE_NUMBER",
        supported_language="en",
    )

    analyzer.registry.remove_recognizer("PhoneRecognizer")
    analyzer.registry.add_recognizer(phone_recognizer)

    coarse_number_recognizer = _create_coarse_number_recognizer()
    analyzer.registry.add_recognizer(coarse_number_recognizer)

    return analyzer


@cache
def _get_anonymizer_engine() -> AnonymizerEngine:
    return AnonymizerEngine()
