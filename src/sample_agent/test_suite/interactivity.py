"""Interactivity tests for the sample agent."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from metisa_common.specification_models import (
    MetisaSpecification,
)

from .._helper import (
    print_message,
    print_success,
    print_suite_title,
)

_IS_INTERACTIVE = False


def test_interactivity(specification: MetisaSpecification):
    """Run interactivity tests."""
    print_suite_title("Interactivity")

    output_dir = os.environ.get("SANDBOX_OUTPUT_DIR", "")
    is_running_local = not output_dir
    if is_running_local:
        output_dir = _create_run_directory()
    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)

    if _IS_INTERACTIVE:
        user_name = input("What is your name? ")
    else:
        user_name = "Fred"

    message = f"Hello {user_name} from the Sample Agent."

    answer_path = output_directory / "answer.txt"
    answer_path.write_text(
        message,
        encoding="utf-8",
    )

    print_success(message)
    print_message(f"Wrote answer to {answer_path}")


# This function is only used when the agent is run without the sandbox.
def _create_run_directory() -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    run_directory = Path.cwd() / ".runs" / f"run-{timestamp}" / "output"
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_directory
