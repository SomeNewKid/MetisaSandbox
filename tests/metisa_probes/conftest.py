from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from metisa_common.specification_helper import parse_specification
from metisa_probes._probe_models import ProbeContext


@pytest.fixture
def probe_context(tmp_path: Path) -> ProbeContext:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    return ProbeContext(
        parse_specification('agent_name = "probe_test"'),
        source_volume=str(source),
        output_volume=str(output),
        work_dir=str(work),
    )


@pytest.fixture
def context_with(probe_context: ProbeContext) -> Callable[..., ProbeContext]:
    def create(**changes: object) -> ProbeContext:
        return replace(
            probe_context,
            specification=replace(probe_context.specification, **changes),
        )

    return create


@pytest.fixture
def read_text(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Replace Linux file reads; unexpected reads never touch the host."""
    reader = Mock()
    monkeypatch.setattr(Path, "read_text", reader)
    return reader
