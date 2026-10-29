import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from metisa_probes import runner
from metisa_probes._probe_models import ProbeContext, ProbeGroup, ProbeResult


@pytest.mark.parametrize("arguments", [[], [""], ["missing.toml"]])
def test_invalid_specification_argument(arguments: list[str]) -> None:
    assert runner.main(arguments) == 1


def test_probe_group_logs_all_results_and_continues_after_exception(
    probe_context: ProbeContext,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    passed = Mock(return_value=ProbeResult.success("passing", "allowed"))
    failed = Mock(return_value=ProbeResult.failure("failing", "policy missing"))
    raised = Mock(side_effect=ValueError("bad metadata"))
    raised.__name__ = "raised"
    final = Mock(return_value=ProbeResult.success("final", "still checked"))
    group = ProbeGroup("example", (passed, failed, raised, final))
    log = tmp_path / "probes.jsonl"
    assert not runner._run_probe_group(group, probe_context, log)
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert records == [
        {"name": "passing", "passed": True, "message": "allowed"},
        {"name": "failing", "passed": False, "message": "policy missing"},
        {
            "name": "example__raised",
            "passed": False,
            "message": "Probe raised an unexpected exception: ValueError: bad metadata",
        },
        {"name": "final", "passed": True, "message": "still checked"},
    ]
    for probe in (passed, failed, raised, final):
        probe.assert_called_once_with(probe_context)
    output = capsys.readouterr().out
    assert "[FAIL] failing" in output
    assert "[FAIL] example__raised" in output
    assert "[PASS]" not in output


@pytest.mark.parametrize("failure", [False, True])
def test_main_aggregates_all_groups(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    tmp_path: Path,
    failure: bool,
) -> None:
    specification = tmp_path / "metisa.toml"
    specification.touch()
    monkeypatch.setattr(
        runner, "load_specification", lambda path: probe_context.specification
    )
    log = tmp_path / "result.jsonl"
    monkeypatch.setattr(runner, "_get_log_path", lambda context: log)
    run_group = Mock(side_effect=[not failure] + [True] * 20)
    monkeypatch.setattr(runner, "_run_probe_group", run_group)
    assert runner.main([str(specification)]) == (1 if failure else 0)
    assert run_group.call_count == 21
    assert len({call.args[0].name for call in run_group.call_args_list}) == 21


def test_log_directory_and_append(probe_context: ProbeContext) -> None:
    log = runner._get_log_path(probe_context)
    assert log == Path(probe_context.output_volume) / ".logs/metisa/metisa_probes.jsonl"
    runner._write_probe_log_entry(log, ProbeResult.success("one", "first"))
    runner._write_probe_log_entry(log, ProbeResult.failure("two", "second"))
    assert [json.loads(line)["name"] for line in log.read_text().splitlines()] == [
        "one",
        "two",
    ]
