"""Performs anonymization of text."""

from __future__ import annotations

from functools import cache
from threading import Lock

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.predefined_recognizers import PhoneRecognizer
from presidio_anonymizer import AnonymizerEngine
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
            "AU_MEDICARE",  # Medicare numbe
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
        anonymizer = _get_anonymizer_engine()

        anonymized = anonymizer.anonymize(
            text=text, analyzer_results=anonymizer_results
        )

    return anonymized.text


def initialize_anonymizer_engine() -> None:
    """Initialize the anonymizer engine by caching it."""
    with _ANALYZER_LOCK:
        _ = _get_analyzer()
    with _ANONYMIZER_LOCK:
        _ = _get_anonymizer_engine()


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

    return analyzer


@cache
def _get_anonymizer_engine() -> AnonymizerEngine:
    return AnonymizerEngine()
