"""Utility functions for the Metisa Probes module."""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import cast


# The function permit_probe_process_spawn is defined in sitecustomize.py,
# so we need to dynamically retrieve it from the sitecustomize module.
# (Ruff and Pylance will complain if the code tries to use
# permit_probe_process_spawn directly.)
def permit_process_spawn() -> AbstractContextManager[None]:
    """Return a context manager that permits process spawning for probes."""
    sitecustomize_module = sys.modules.get("sitecustomize")
    if sitecustomize_module is None:
        raise RuntimeError("sitecustomize is not loaded.")

    permit_candidate = vars(sitecustomize_module).get("permit_probe_process_spawn")
    if not callable(permit_candidate):
        raise RuntimeError(
            "sitecustomize does not provide permit_probe_process_spawn()."
        )

    permit = cast(
        Callable[[], AbstractContextManager[None]],
        permit_candidate,
    )
    return permit()
