"""Models providing abstractions for the Docker sandbox."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SandboxContext:
    """Contextual information for a Docker sandbox."""

    run_identifier: str
    workload_container_name: str

    private_network_name: str
    egress_network_name: str

    host_run_path: Path
    host_output_path: Path
    host_logs_path: Path
