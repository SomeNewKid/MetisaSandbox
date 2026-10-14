"""Manages the host filesystem state for the Prompt Guard container."""

from __future__ import annotations

from pathlib import Path

from ..sandbox_context import SandboxContext
from ..utilities.workspace_helper import copy_directories_into_staged

PROMPT_GUARD_MODULE_NAME = "metisa_prompt_guard"


def create_staged_source_directory(
    sandbox_context: SandboxContext,
) -> Path:
    """Create a staged source directory for the sandbox context."""
    local_source_path = Path.cwd() / "src"
    staged_source_path = sandbox_context.host_run_path / "prompt_guard_source"
    staged_source_path.mkdir(parents=True, exist_ok=False)

    copy_directories_into_staged(
        local_source_path,
        staged_source_path,
        [
            PROMPT_GUARD_MODULE_NAME,
        ],
    )

    return staged_source_path
