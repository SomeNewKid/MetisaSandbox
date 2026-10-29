from unittest.mock import Mock

import pytest

from metisa_probes._kernel import _network_probes as probes
from metisa_probes._probe_models import ProbeContext


@pytest.mark.parametrize(
    "value,passed",
    [
        ("1024\n", True),
        ("0", False),
        ("1023", False),
        ("1025", False),
        ("invalid", False),
        ("", False),
    ],
)
def test_privileged_port_boundary(
    read_text: Mock, probe_context: ProbeContext, value: str, passed: bool
) -> None:
    read_text.return_value = value
    result = probes.unprivileged_port_start_is_1024(probe_context)
    assert result.passed is passed
    assert result.name == "kernel__network__unprivileged_port_start_is_1024"


def test_sysctl_read_error(read_text: Mock, probe_context: ProbeContext) -> None:
    read_text.side_effect = OSError("sysctl unavailable")
    result = probes.unprivileged_port_start_is_1024(probe_context)
    assert not result.passed
    assert "sysctl unavailable" in result.message
