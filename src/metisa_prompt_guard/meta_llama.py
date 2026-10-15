"""Uses the Meta's Llama-Prompt-Guard-2 model to classify text."""

from __future__ import annotations

from functools import cache
from threading import Lock

import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    TextClassificationPipeline,
)

from .models import Indicator

_MODEL_LOCATION = "/models/llama-prompt-guard"
_MAX_TOKENS = 512
_OVERLAP_TOKENS = 128
_CLASSIFIER_LOCK = Lock()


def get_indicators(
    text: str,
) -> tuple[Indicator, ...]:
    """Return indicators resulting from classification by Llama Prompt Guard."""
    if not text.strip():
        return ()

    with _CLASSIFIER_LOCK:
        classifier = _get_classifier()
        if (
            not classifier.model
            or not classifier.model.config
            or not classifier.model.config.id2label
        ):
            raise RuntimeError("Classifier model not available.")

        tokenizer = classifier.tokenizer
        if tokenizer is None:
            raise ValueError("Classifier tokenizer not available.")

        encoded = tokenizer(
            text,
            max_length=_MAX_TOKENS,
            stride=_OVERLAP_TOKENS,
            truncation=True,
            return_overflowing_tokens=True,
            padding=True,
            return_tensors="pt",
        )

        number_of_chunks = encoded["input_ids"].shape[0]

        with torch.inference_mode():
            for index in range(number_of_chunks):
                model_inputs = {}
                for name in tokenizer.model_input_names:
                    if name in encoded:
                        chunk_tensor = encoded[name][index : index + 1]
                        model_inputs[name] = chunk_tensor.to(classifier.device)

                output = classifier.model(**model_inputs)
                predicted_class = output.logits.argmax(dim=-1).item()
                label = classifier.model.config.id2label[predicted_class]

                if label == "MALICIOUS":
                    return (
                        Indicator(
                            "meta_llama_prompt_guard",
                            "The text was classified as having malicious content.",
                        ),
                    )

    return ()


def initialize_classifier() -> None:
    """Initialize the classifier by loading the model and tokenizer into memory."""
    with _CLASSIFIER_LOCK:
        _ = _get_classifier()


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
