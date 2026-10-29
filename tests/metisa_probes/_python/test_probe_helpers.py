import sys
from contextlib import nullcontext
from types import ModuleType
from unittest.mock import Mock

import pytest

from metisa_probes._python import _probe_helpers as helpers


def test_spawn_scope_comes_from_sitecustomize(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("sitecustomize")
    permit = Mock(return_value=nullcontext())
    monkeypatch.setattr(module, "permit_probe_process_spawn", permit, raising=False)
    monkeypatch.setitem(sys.modules, "sitecustomize", module)
    with helpers.permit_process_spawn():
        permit.assert_called_once_with()


@pytest.mark.parametrize("loaded", [False, True])
def test_missing_spawn_scope_fails(
    monkeypatch: pytest.MonkeyPatch, loaded: bool
) -> None:
    if loaded:
        monkeypatch.setitem(sys.modules, "sitecustomize", ModuleType("sitecustomize"))
    else:
        monkeypatch.delitem(sys.modules, "sitecustomize", raising=False)
    with pytest.raises(RuntimeError, match="sitecustomize"):
        helpers.permit_process_spawn()
