"""Uses the Koala Text Moderation model to moderate text."""

from __future__ import annotations

from functools import cache
from threading import Lock
from typing import cast

import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    TextClassificationPipeline,
)

_MODEL_LOCATION = "/models/koala-text-moderation"
_MAX_TOKENS = 512
_OVERLAP_TOKENS = 128
_CATEGORY_THRESHOLD = 0.15
_CLASSIFIER_LOCK = Lock()


def get_labels(
    text: str,
) -> tuple[str, ...]:
    """Return labels resulting from classification by Koala Text Moderation."""
    if not text.strip():
        return ()

    labels: list[str] = []

    with _CLASSIFIER_LOCK:
        classifier = _get_classifier()
        if (
            not classifier.model
            or not classifier.model.config
            or not classifier.model.config.id2label
        ):
            raise RuntimeError("Classifier model not available.")

        # There is a type-checking ambiguity in Transformers’ annotation.
        # id2label: dict[int, str] | dict[str, str] | None
        # `cast` informs the type checker;
        # it performs no runtime conversion or validation.
        id_to_label = cast(dict[int, str], classifier.model.config.id2label)

        tokenizer = classifier.tokenizer
        if not tokenizer:
            raise RuntimeError("Classifier tokenizer not available.")

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
                scores = torch.softmax(output.logits, dim=-1)
                chunk_scores = scores[0].tolist()

                for class_id, score in enumerate(chunk_scores):
                    label = id_to_label[class_id]
                    if label != "OK" and score >= _CATEGORY_THRESHOLD:
                        labels.append(_get_category(label))

    return tuple(set(labels))  # set removes duplicates


def initialize_classifier() -> None:
    """Initialize the classifier by loading the model and tokenizer into memory."""
    with _CLASSIFIER_LOCK:
        _ = _get_classifier()


# https://huggingface.co/KoalaAI/Text-Moderation
def _get_category(
    label: str,
) -> str:
    match label.upper():
        case "S":
            return "sexual"
        case "H":
            return "hate"
        case "V":
            return "violence"
        case "HR":
            return "harassment"
        case "SH":
            return "self-harm"
        case "S3":
            return "sexual/minors"
        case "H2":
            return "hate/threatening"
        case "V2":
            return "violence/graphic"
        case _:
            return f"unknown/{label}"


@cache
def _get_classifier() -> TextClassificationPipeline:
    tokenizer = AutoTokenizer.from_pretrained(
        _MODEL_LOCATION,
        local_files_only=True,
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        _MODEL_LOCATION,
        local_files_only=True,
        use_safetensors=True,  # makes the intended weights file explicit
    )

    return TextClassificationPipeline(
        model=model,
        tokenizer=tokenizer,
        device=-1,  # run inference on the CPU, even if a GPU is available
    )
