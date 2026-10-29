from unittest.mock import Mock

import pytest

from metisa_probes._kernel import _linux_capability_probes as probes
from metisa_probes._probe_models import ProbeContext

_FIELDS = ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")


def test_all_capabilities_empty(read_text: Mock, probe_context: ProbeContext) -> None:
    read_text.return_value = "Name: python\n" + "\n".join(
        f"{field}: 0000000000000000" for field in _FIELDS
    )
    result = probes.capability_sets_are_empty(probe_context)
    assert result.passed
    assert result.name == "kernel__linux_capabilities__capability_sets_are_empty"


@pytest.mark.parametrize("field", _FIELDS)
@pytest.mark.parametrize("value", ["1", "ff", "invalid", None])
def test_each_capability_is_required_and_empty(
    read_text: Mock, probe_context: ProbeContext, field: str, value: str | None
) -> None:
    read_text.return_value = "\n".join(
        f"{name}: {value if name == field else '0'}"
        for name in _FIELDS
        if name != field or value is not None
    )
    result = probes.capability_sets_are_empty(probe_context)
    assert not result.passed
    assert field in result.message


def test_status_unreadable(read_text: Mock, probe_context: ProbeContext) -> None:
    read_text.side_effect = OSError("missing status")
    assert not probes.capability_sets_are_empty(probe_context).passed
