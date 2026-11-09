"""Define tool execution errors safe to report through MCP."""

from __future__ import annotations


class KnownSafeError(RuntimeError):
    """Represent an expected failure with a fixed public message."""
