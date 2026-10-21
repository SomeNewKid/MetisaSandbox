"""Embeddings tests for the sample agent."""

from __future__ import annotations

import json
import os
from pathlib import Path

from metisa_common.specification_models import (
    Capability,
    MetisaSpecification,
)

from ..helper import (
    get_mcp_server_tool_result,
    print_caution,
    print_disabled,
    print_elapsed_time,
    print_failure,
    print_message,
    print_success,
    print_suite_title,
)

_SKIP_EMBEDDINGS_TESTS = True


def test_embeddings(specification: MetisaSpecification):
    """Run Embeddings tests."""
    print_suite_title("Embeddings")

    if _SKIP_EMBEDDINGS_TESTS:
        print_caution("Embeddings capability is being skipped.")
        return

    if Capability.EMBEDDINGS not in specification.capabilities:
        print_disabled("Embeddings capability not declared.")
        return

    filename = "Employee Handbook.pdf"
    _get_get_matching_chunks(filename, "What are our company values?")
    print(flush=True)
    _get_get_matching_chunks(filename, "What is the email of the Compliance Officer?")


def _get_get_matching_chunks(filename: str, prompt: str) -> None:
    with print_elapsed_time():
        try:
            print_message(prompt)
            serialized_data = get_mcp_server_tool_result(
                tool_name="get_matching_chunks",
                params={"filename": filename, "prompt": prompt},
            )
            if not serialized_data:
                print_failure("No JSON response received")
                return

            _save_raw_response("payload.txt", serialized_data)
            payload = json.loads(serialized_data)
            if not payload:
                print_failure("Received payload had entries.")
                return
            _save_raw_response("payload.json", json.dumps(payload, indent=2))
            if not isinstance(payload, dict):
                print_failure("Received payload was not a dictionary.")
                return
            data = payload.get("data", None)
            if data is None:
                print_failure("Received payload had no data.")
                return
            if not isinstance(data, list):
                print_failure("Received payload data was not a list.")
                return

            any_valid = False

            separator = ""

            for item in data:
                if not isinstance(item, str):
                    print_failure("Received payload data item was not a string.")
                    return

                if not item:
                    continue

                if separator:
                    print(separator, flush=True)
                text = item[0:200].strip() + "..." if len(item) > 200 else item
                print_success(text)
                any_valid = True
                separator = "---"

            if not any_valid:
                print_failure("Received payload data had no non-empty items.")

        except Exception as error:
            print_failure(
                "Retrieve Embeddings sample error:",
                type(error).__name__,
                str(error),
            )


def _save_raw_response(
    filename: str,
    content: str,
) -> None:
    output_dir = os.environ.get("SANDBOX_OUTPUT_DIR", "")
    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_file = output_directory / filename
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(content)
