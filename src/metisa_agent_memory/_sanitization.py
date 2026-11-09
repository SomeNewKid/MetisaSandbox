"""Utility methods for validation."""

from metisa_common.utilities.type_models import (
    sanitize_content,
    sanitize_json_object,
)

from ._models import Episode, Memory


def sanitize_episode(
    episode: Episode,
) -> None:
    """Sanitize the properties of the specified Episode."""
    episode.content = sanitize_json_object(episode.content)
    episode.metadata = sanitize_json_object(episode.metadata)


def sanitize_memory(
    memory: Memory,
) -> None:
    """Sanitize the properties of the specified Memory."""
    memory.subject = sanitize_content(memory.subject)
    memory.text = sanitize_content(memory.text)
    memory.content = sanitize_json_object(memory.content)
    memory.metadata = sanitize_json_object(memory.metadata)
