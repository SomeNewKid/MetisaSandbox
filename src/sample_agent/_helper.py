"""Utility functions for the Sample Agent."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager

_RESET = "\033[0m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_GREY = "\033[38;5;244m"


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


def print_suite_title(
    title: str,
) -> None:
    """Print a suite title."""
    print()
    print("-" * 30)
    if title:
        print(title)
    print(flush=True)


def print_message(*args: object) -> None:
    """Print a message."""
    print(*args, flush=True)


def print_success(*args: object) -> None:
    """Print a success message."""
    _print_colored(_GREEN, "✓ ", *args)


def print_failure(*args: object) -> None:
    """Print a failure message."""
    _print_colored(_RED, "x ", *args)


def print_disabled(*args: object) -> None:
    """Print a skipped message."""
    _print_colored(_GREY, *args)


def print_caution(*args: object) -> None:
    """Print a caution message."""
    _print_colored(_YELLOW, *args)


def _print_colored(color: str, *args: object) -> None:
    colored_args = [f"{color}{arg}{_RESET}" for arg in args]
    print(*colored_args, flush=True)
