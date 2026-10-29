import pytest

from metisa_probes._probe_models import ProbeResult


@pytest.mark.parametrize("passed", [False, True])
def test_result_factories_preserve_name_and_message(passed: bool) -> None:
    factory = ProbeResult.success if passed else ProbeResult.failure
    result = factory("probe-name", "diagnostic detail")
    assert result.name == "probe-name"
    assert result.passed is passed
    assert result.message == "diagnostic detail"
