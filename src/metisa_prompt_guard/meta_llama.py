"""Uses the Meta's Llama-Prompt-Guard-2 model to classify text."""

from __future__ import annotations

from functools import cache
from threading import Lock

from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    TextClassificationPipeline,
)

from .models import Indicator

_MODEL_LOCATION = "/models/llama-prompt-guard"
_CLASSIFIER_LOCK = Lock()


def get_indicators(
    text: str,
) -> tuple[Indicator, ...]:
    """Return indicators resulting from classification by Llama Prompt Guard."""
    indicators: list[Indicator] = []

    with _CLASSIFIER_LOCK:
        classifier = _get_classifier()
        classification: list[dict[str, object]] = classifier(text)

    indicators.extend(_get_indicators(classification))

    return tuple(indicators)


def initialize_classifier() -> None:
    """Initialize the classifier by loading the model and tokenizer into memory."""
    with _CLASSIFIER_LOCK:
        _ = _get_classifier()


def _get_indicators(
    classification: list[dict[str, object]],
) -> tuple[Indicator, ...]:
    indicators: list[Indicator] = []

    for item in classification:
        label = item.get("label")
        if label == "MALICIOUS":
            indicator = Indicator(
                "meta_llama_prompt_guard",
                "The text was classified as having malicious content.",
            )
            indicators.append(indicator)

    return tuple(indicators)


@cache
def _get_classifier() -> TextClassificationPipeline:
    tokenizer = AutoTokenizer.from_pretrained(
        _MODEL_LOCATION,
        local_files_only=True,
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        _MODEL_LOCATION,
        local_files_only=True,
    )
    model.config.id2label = {
        0: "BENIGN",
        1: "MALICIOUS",
    }
    model.config.label2id = {
        "BENIGN": 0,
        "MALICIOUS": 1,
    }

    return TextClassificationPipeline(
        model=model,
        tokenizer=tokenizer,
        device=-1,  # run inference on the CPU, even if a GPU is available
    )
