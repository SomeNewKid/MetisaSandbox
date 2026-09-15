"""Command-line interface for the application."""

from __future__ import annotations

import os
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Run the sample agent workload."""

    output_dir = Path(os.environ.get("SANDBOX_OUTPUT_DIR", "."))
    output_dir.mkdir(parents=True, exist_ok=True)

    answer_path = output_dir / "answer.txt"
    answer_path.write_text(
        "Hello from the Sample Agent.",
        encoding="utf-8",
    )

    print("Hello from the Sample Agent.")
    print(f"Wrote answer to {answer_path}")

    return 0
