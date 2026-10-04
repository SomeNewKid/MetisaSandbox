"""Manages the host filesystem state for the MCP Server container."""

from __future__ import annotations

from pathlib import Path

from ..sandbox_context import SandboxContext
from ..utilities.workspace_helper import copy_directories_into_staged

LANDLOCK_MODULE_NAME = "metisa_landlock"
MCP_SERVER_MODULE_NAME = "metisa_mcp_server"

_COMMON_MODULE_NAME = "metisa_common"


def create_staged_source_directory(
    sandbox_context: SandboxContext,
) -> Path:
    """Create a staged source directory for the sandbox context."""
    local_source_path = Path.cwd() / "src"
    staged_source_path = sandbox_context.host_run_path / "mcp_server_source"
    staged_source_path.mkdir(parents=True, exist_ok=False)

    copy_directories_into_staged(
        local_source_path,
        staged_source_path,
        [
            LANDLOCK_MODULE_NAME,
            _COMMON_MODULE_NAME,
            MCP_SERVER_MODULE_NAME,
        ],
    )

    return staged_source_path
