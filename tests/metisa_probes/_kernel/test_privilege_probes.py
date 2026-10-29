from unittest.mock import Mock

import pytest

from metisa_probes._kernel import _privilege_probes as probes
from metisa_probes._probe_models import ProbeContext


@pytest.mark.parametrize(
    "text,passed",
    [
        ("Name: python\nNoNewPrivs:\t1\n", True),
        ("NoNewPrivs: 0", False),
        ("NoNewPrivs: invalid", False),
        ("NoNewPrivs 1", False),
        ("Name: python", False),
    ],
)
def test_no_new_privileges(
    read_text: Mock, probe_context: ProbeContext, text: str, passed: bool
) -> None:
    read_text.return_value = text
    result = probes.no_new_privileges_is_enabled(probe_context)
    assert result.passed is passed
    assert result.name == "kernel__privileges__no_new_privileges_is_enabled"
    assert result.message


def test_status_read_error(read_text: Mock, probe_context: ProbeContext) -> None:
    read_text.side_effect = PermissionError("status denied")
    result = probes.no_new_privileges_is_enabled(probe_context)
    assert not result.passed
    assert "status denied" in result.message
