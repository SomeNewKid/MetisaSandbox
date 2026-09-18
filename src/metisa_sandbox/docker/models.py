"""Models providing abstractions for the Docker sandbox."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SandboxContext:
    image_name: str
    image_tag: str
    identifier: str
    network_name: str
    host_run_path: Path
    host_source_path: Path
    host_output_path: Path

    common_module_name: str = "metisa_common"
    runner_module_name: str = "metisa_runner"
    probes_module_name: str = "metisa_probes"
    guest_source_dir: str = "/sandbox-source"
    guest_output_dir: str = "/sandbox-output"
    guest_work_dir: str = "/sandbox-work"
