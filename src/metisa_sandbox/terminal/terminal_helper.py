"""
Provides utility methods for working with the Terminal.
"""

from __future__ import annotations

import msvcrt
import sys


def get_first_argument(argv: list[str] | None = None) -> str:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        return ""

    return args[0]


def get_user_approval(question: str) -> bool:
    print(f"{question} ", end="", flush=True)
    key = msvcrt.getwch()
    if key.lower() == "y":
        print("Y")
        return True
    print("N")
    return False


def print_info(message: str) -> None:
    print(f"{message}")


def print_warning(message: str) -> None:
    print(f"[WARN] {message}")


def print_error(message: str) -> None:
    print(f"[ERROR] {message}")
