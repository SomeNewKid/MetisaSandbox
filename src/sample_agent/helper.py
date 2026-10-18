"""Utility functions for the Sample Agent."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager


@contextmanager
def print_elapsed_time() -> Generator[None, None, None]:
    """Print the elapsed time after the wrapped block finishes."""
    started = time.monotonic()

    try:
        yield
    finally:
        elapsed_seconds = time.monotonic() - started
        duration = _format_elapsed_time(elapsed_seconds)
        print(f"[Elapsed: {duration}]", flush=True)


def _format_elapsed_time(elapsed_seconds: float) -> str:
    if elapsed_seconds < 1:
        milliseconds = int(elapsed_seconds * 1000)
        return f"{milliseconds}ms"

    whole_seconds = int(elapsed_seconds)
    minutes, seconds = divmod(whole_seconds, 60)

    if minutes:
        return f"{minutes}m {seconds}s"

    return f"{seconds}s"