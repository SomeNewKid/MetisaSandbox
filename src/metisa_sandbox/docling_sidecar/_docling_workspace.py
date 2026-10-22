"""Manages the host filesystem state for the Docling container."""

from __future__ import annotations

from pathlib import Path

from .._sandbox_models import SandboxContext
from .._utilities._workspace_helper import copy_directories_into_staged

DOCLING_MODULE_NAME = "metisa_docling"


def create_staged_source_directory(
    sandbox_context: SandboxContext,
) -> Path:
    """Create a staged source directory for the sandbox context."""
    local_source_path = Path.cwd() / "src"
    staged_source_path = sandbox_context.host_run_path / "docling_source"
    staged_source_path.mkdir(parents=True, exist_ok=False)

    copy_directories_into_staged(
        local_source_path,
        staged_source_path,
        [
            DOCLING_MODULE_NAME,
        ],
    )

    return staged_source_path
