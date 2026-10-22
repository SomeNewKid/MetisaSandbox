"""Manages the host filesystem state for the Metisa container."""

from __future__ import annotations

from pathlib import Path

from .._sandbox_models import SandboxContext
from .._utilities._workspace_helper import copy_directories_into_staged

LANDLOCK_MODULE_NAME = "metisa_landlock"

_COMMON_MODULE_NAME = "metisa_common"
_RUNNER_MODULE_NAME = "metisa_runner"
_PROBES_MODULE_NAME = "metisa_probes"


def create_staged_source_directory(
    sandbox_context: SandboxContext,
    workload_module: str,
) -> Path:
    """Create a staged source directory for the sandbox context."""
    local_source_path = Path.cwd() / "src"
    staged_source_path = sandbox_context.host_run_path / "metisa_source"
    staged_source_path.mkdir(parents=True, exist_ok=False)

    copy_directories_into_staged(
        local_source_path,
        staged_source_path,
        [
            LANDLOCK_MODULE_NAME,
            _COMMON_MODULE_NAME,
            _RUNNER_MODULE_NAME,
            _PROBES_MODULE_NAME,
            workload_module,
        ],
    )

    return staged_source_path
