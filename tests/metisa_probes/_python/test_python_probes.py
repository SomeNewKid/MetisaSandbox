import importlib.metadata
import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from metisa_probes._probe_models import ProbeContext, ProbeFunction
from metisa_probes._python import _python_probes as probes


@pytest.mark.parametrize(
    "prefix,base,executable,passed",
    [
        ("/opt/metisa-venv", "/usr/local", "/opt/metisa-venv/bin/python", True),
        ("/usr/local", "/usr/local", "/usr/local/bin/python", False),
        ("/other", "/usr/local", "/other/bin/python", False),
        ("/opt/metisa-venv", "/usr/local", "/usr/local/bin/python", False),
    ],
)
def test_virtual_environment(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    prefix: str,
    base: str,
    executable: str,
    passed: bool,
) -> None:
    monkeypatch.setattr(sys, "prefix", prefix)
    monkeypatch.setattr(sys, "base_prefix", base)
    monkeypatch.setattr(sys, "executable", executable)
    assert (
        probes.metisa_python_virtual_environment_is_active(probe_context).passed
        is passed
    )


@pytest.mark.parametrize(
    "mode", ["valid", "missing_file", "not_loaded", "no_location", "wrong_location"]
)
def test_sitecustomize_origin(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    tmp_path: Path,
    mode: str,
) -> None:
    monkeypatch.setattr(probes.sysconfig, "get_path", lambda name: str(tmp_path))
    if mode != "missing_file":
        (tmp_path / "sitecustomize.py").touch()
    module = ModuleType("sitecustomize")
    if mode != "no_location":
        module.__file__ = str(
            tmp_path / ("wrong.py" if mode == "wrong_location" else "sitecustomize.py")
        )
    if mode == "not_loaded":
        monkeypatch.delitem(sys.modules, "sitecustomize", raising=False)
    else:
        monkeypatch.setitem(sys.modules, "sitecustomize", module)
    assert probes.sitecustomize_module_is_active(probe_context).passed is (
        mode == "valid"
    )


@pytest.mark.parametrize("mode", ["denied", "allowed", "unexpected"])
def test_denied_imports(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, mode: str
) -> None:
    operation = Mock(
        side_effect=ModuleNotFoundError("denied")
        if mode == "denied"
        else RuntimeError("broken import")
        if mode == "unexpected"
        else None
    )
    monkeypatch.setattr(probes.importlib, "import_module", operation)
    result = probes.denied_python_modules_cannot_be_imported(probe_context)
    assert result.passed is (mode == "denied"), result.message
    assert {call.args[0] for call in operation.call_args_list} == {
        "_ctypes",
        "ctypes",
        "ensurepip",
        "pip",
        "setuptools",
        "wheel",
    }


@pytest.mark.parametrize(
    "probe",
    [
        probes.ordinary_imports_from_writable_locations_are_denied,
        probes.file_location_imports_from_writable_locations_are_denied,
    ],
)
@pytest.mark.parametrize("mode", ["denied", "allowed", "unexpected"])
def test_writable_code_imports(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    tmp_path: Path,
    probe: ProbeFunction,
    mode: str,
) -> None:
    roots = (tmp_path / "output", tmp_path / "work", tmp_path / "tmp")
    for root in roots:
        root.mkdir(exist_ok=True)
    monkeypatch.setattr(probes, "_DENIED_CODE_ROOTS", roots)
    original_path = sys.path.copy()
    failure = (
        ModuleNotFoundError("policy")
        if mode == "denied"
        else RuntimeError("import broken")
        if mode == "unexpected"
        else None
    )
    if probe is probes.ordinary_imports_from_writable_locations_are_denied:
        monkeypatch.setattr(
            probes.importlib, "import_module", Mock(side_effect=failure)
        )
    elif failure:
        monkeypatch.setattr(
            probes.importlib.util, "spec_from_file_location", Mock(side_effect=failure)
        )
    result = probe(probe_context)
    assert result.passed is (mode == "denied"), result.message
    assert sys.path == original_path
    assert not [path for root in roots for path in root.glob("metisa_probe_*.py")]


@pytest.mark.parametrize("mode", ["denied", "allowed", "wrong_exit", "spawn_error"])
def test_writable_script_startup(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    tmp_path: Path,
    mode: str,
) -> None:
    monkeypatch.setattr(probes, "_DENIED_CODE_ROOTS", (tmp_path,))
    monkeypatch.setattr(probes, "permit_process_spawn", nullcontext)
    run = Mock(
        return_value=Mock(
            returncode=126 if mode == "denied" else 0 if mode == "allowed" else 1
        )
    )
    if mode == "spawn_error":
        run.side_effect = OSError("cannot start")
    monkeypatch.setattr(probes.subprocess, "run", run)
    result = probes.scripts_from_writable_locations_cannot_be_started(probe_context)
    assert result.passed is (mode == "denied"), result.message
    assert run.call_args.kwargs["env"]["METISA_RUNTIME_ROLE"] == "workload"
    assert not list(tmp_path.glob("metisa_probe_*.py"))


@pytest.mark.parametrize(
    "probe", [probes.pip_entry_point_is_absent, probes.pip3_entry_point_is_absent]
)
@pytest.mark.parametrize("location", ["absent", "path", "venv"])
def test_packaging_commands(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    location: str,
) -> None:
    monkeypatch.setattr(
        probes.shutil,
        "which",
        lambda name: "/custom/pip" if location == "path" else None,
    )
    monkeypatch.setattr(Path, "exists", lambda self: location == "venv")
    assert probe(probe_context).passed is (location == "absent")


@pytest.mark.parametrize(
    "probe",
    [
        probes.pip_module_is_absent,
        probes.wheel_module_is_absent,
        probes.ensurepip_module_is_absent,
        probes.setuptools_module_is_absent,
        probes.pkg_resources_module_is_absent,
        probes.distutils_hack_module_is_absent,
    ],
)
@pytest.mark.parametrize("mode", ["absent", "present", "error"])
def test_packaging_module_discovery(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    mode: str,
) -> None:
    finder = Mock(
        return_value=Mock(origin="/installed/module.py") if mode == "present" else None
    )
    if mode == "error":
        finder.side_effect = ImportError("cannot inspect")
    monkeypatch.setattr(probes.importlib.machinery.PathFinder, "find_spec", finder)
    assert probe(probe_context).passed is (mode == "absent")


@pytest.mark.parametrize("installed", [None, "pip", "setuptools", "wheel"])
def test_packaging_distribution_metadata(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, installed: str | None
) -> None:
    def distribution(name: str) -> Mock:
        if name != installed:
            raise importlib.metadata.PackageNotFoundError(name)
        return Mock(metadata={"Name": name}, version="1.0")

    monkeypatch.setattr(probes.importlib.metadata, "distribution", distribution)
    result = probes.package_management_metadata_is_absent(probe_context)
    assert result.passed is (installed is None)
    if installed:
        assert installed in result.message


@pytest.mark.parametrize(
    "artifact",
    [None, "pip", "wheel.py", "setuptools-1.0.dist-info", "distutils-precedence.pth"],
)
def test_physical_packaging_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    tmp_path: Path,
    artifact: str | None,
) -> None:
    monkeypatch.setattr(
        probes.sysconfig, "get_paths", lambda: {"purelib": str(tmp_path)}
    )
    monkeypatch.setattr(probes, "_PYTHON_LIBRARY_ROOTS", ())
    if artifact:
        (tmp_path / artifact).touch()
    result = probes.python_packaging_artifacts_are_absent(probe_context)
    assert result.passed is (artifact is None)
    if artifact:
        assert artifact in result.message
