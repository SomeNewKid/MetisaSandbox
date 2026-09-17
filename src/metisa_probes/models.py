"""Models used in the Metisa Probes module."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ProbeContext:
    """Context specific to the AI agent workload."""

    output_volume: str = "/sandbox-output"
    source_volume: str = "/sandbox-source"
    work_dir: str = "/sandbox-work"


@dataclass(frozen=True)
class ProbeResult:
    """Result of one sandbox probe."""

    name: str
    passed: bool
    message: str

    @classmethod
    def success(cls, name: str, message: str) -> ProbeResult:
        """Create a passing probe result"""
        return cls(name=name, passed=True, message=message)

    @classmethod
    def failure(cls, name: str, message: str) -> ProbeResult:
        """Create a failing probe result"""
        return cls(name=name, passed=False, message=message)


ProbeFunction = Callable[[ProbeContext], ProbeResult]


@dataclass(frozen=True)
class ProbeGroup:
    """A named collection of probes."""

    name: str
    probes: tuple[ProbeFunction, ...]
