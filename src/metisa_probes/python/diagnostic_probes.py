"""Probes which perform diagnostic checks on the system."""

from __future__ import annotations

import sysconfig

from ..models import ProbeContext, ProbeGroup, ProbeResult


def purelib_path(probe_context: ProbeContext) -> ProbeResult:
    """Get the path to the purelib directory of the current Python environment."""
    probe_name = "python__diagnostic__purelib_path"
    path = sysconfig.get_path("purelib")
    message = f"Purelib path is {path!r}."
    return ProbeResult.success(probe_name, message)


DIAGNOSTIC_PROBES = ProbeGroup(
    name="diagnostic",
    probes=(purelib_path,),
)
