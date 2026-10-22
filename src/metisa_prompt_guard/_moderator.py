"""Run checks for labeled content."""

from __future__ import annotations

from ._koala_moderation import get_labels as get_koala_labels


def get_labels(
    text: str,
) -> tuple[str, ...]:
    """Get the labels for the provided text."""
    labels: list[str] = []
    try:
        labels.extend(get_koala_labels(text))
    except Exception as error:
        # Ensure that, if an error occurs, we don't return an empty list of labels,
        # which would incorrectly indicate that no issues were found.
        print("Exception occurred during get_labels:", str(error))
        labels.append("UNKNOWN")
    _print_result(text, labels)
    return tuple(labels)


def _print_result(
    text: str,
    labels: list[str],
) -> None:
    print("-" * 30)
    text_summary = text if len(text) < 200 else text[:200]
    print("Text:", text_summary)
    if not labels:
        print("(No labels)")
        return
    for label in labels:
        print(label)
