"""Models for the Prompt Guard module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Indicator:
    """Represents a finding identified by a check."""

    check_id: str
    explanation: str


class Check(Protocol):
    """Represents a check that can identify findings."""

    @property
    def id(self) -> str:
        """Return the unique identifier for this check."""
        ...

    def run(self, text: str) -> Indicator | None:
        """Run the check on the given text and return a finding if applicable."""
        ...
