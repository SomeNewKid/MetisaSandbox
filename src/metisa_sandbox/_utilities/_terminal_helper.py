"""Provides utility methods for working with the Terminal."""

from __future__ import annotations

import msvcrt
import sys


def get_first_argument(
    argv: list[str] | None = None,
) -> str:
    """Get the first command-line argument, or an empty string if none are provided."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        return ""

    return args[0]


def get_user_approval(
    question: str,
) -> bool:
    """Prompt the user with a yes/no question and return True if the answer is 'y'."""
    print(f"{question} ", end="", flush=True)
    key = msvcrt.getwch()
    if key.lower() == "y":
        print("Y")
        return True
    print("N")
    return False


def print_info(
    message: str,
) -> None:
    """Print an informational message to the terminal."""
    print(f"{message}")


def print_warning(
    message: str,
) -> None:
    """Print a warning message to the terminal."""
    print(f"[WARN] {message}")


def print_error(
    message: str,
) -> None:
    """Print an error message to the terminal."""
    print(f"[ERROR] {message}")
