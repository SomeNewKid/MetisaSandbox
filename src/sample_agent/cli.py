"""Command-line interface for the application."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import requests

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

    url = "https://example.com"
    try:
        response = requests.get(url)
        status_code = response.status_code
        if status_code == 200:
            html = response.text
            if html:
                title = _get_title_from_html(response.text)
                if title:
                    print(f"example.com page title: {title}")
                else:
                    print("Could not get example.com page title.")
            else:
                print("Received empty response.")
        else:
            print(f"Failed to get response.  Status code: {status_code}")
    except Exception as error:
        print("Exception", error)

    return 0


# This function is only used when the agent is run without the sandbox.
def _create_run_directory() -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    run_directory = Path.cwd() / ".runs" / f"run-{timestamp}" / "output"
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_directory


def _get_title_from_html(html: str) -> str:
    tag = "title"
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    open_tag_index = html.find(open_tag)
    close_tag_index = html.find(close_tag)
    if open_tag_index < 0 or close_tag_index < 0:
        return ""
    return html[open_tag_index + len(open_tag) : close_tag_index]
