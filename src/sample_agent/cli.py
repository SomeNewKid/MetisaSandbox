"""Command-line interface for the application."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

IS_INTERACTIVE = False


def main(
    argv: list[str] | None = None,
) -> int:
    """Run the sample agent workload."""
    output_dir = os.environ.get("SANDBOX_OUTPUT_DIR", "")
    if not output_dir:
        output_dir = _create_run_directory()
    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)

    if IS_INTERACTIVE:
        user_name = input("What is your name? ")
    else:
        user_name = "Fred"

    message = f"Hello {user_name} from the Sample Agent."

    answer_path = output_directory / "answer.txt"
    answer_path.write_text(
        message,
        encoding="utf-8",
    )

    print(message)
    print(f"Wrote answer to {answer_path}")

    return 0


def _create_run_directory() -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    run_directory = Path.cwd() / ".runs" / f"run-{timestamp}" / "output"
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_directory
