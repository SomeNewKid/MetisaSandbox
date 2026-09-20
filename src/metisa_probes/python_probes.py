"""Probes related to the Python framework."""

from __future__ import annotations

import importlib
import importlib.machinery
import importlib.metadata
import importlib.util
import shutil
import subprocess
import sys
import sysconfig
import uuid
from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult
from .probe_helpers import permit_process_spawn

_DENIED_MODULE_NAMES = (
    "_ctypes",
    "ctypes",
    "ensurepip",
    "pip",
    "setuptools",
    "wheel",
)
_DENIED_CODE_ROOTS = (
    Path("/sandbox-output"),
    Path("/sandbox-work"),
    Path("/tmp"),
)
_PROBE_MODULE_SOURCE = "PROBE_EXECUTED = True\n"


def metisa_python_virtual_environment_is_active(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python is running from the Metisa virtual environment."""
    probe_name = "python__metisa_python_virtual_environment_is_active"
    expected_prefix = Path("/opt/metisa-venv")

    actual_prefix = Path(sys.prefix)
    base_prefix = Path(sys.base_prefix)

    if actual_prefix == base_prefix:
        message = (
            "Python is not running in a virtual environment: "
            f"sys.prefix and sys.base_prefix are both {actual_prefix}."
        )
        return ProbeResult.failure(probe_name, message)

    if actual_prefix != expected_prefix:
        message = (
            f"Expected virtual environment {expected_prefix}, got {actual_prefix}."
        )
        return ProbeResult.failure(probe_name, message)

    executable = Path(sys.executable)

    try:
        executable.relative_to(expected_prefix)
    except ValueError:
        message = (
            f"Python executable {executable} is outside "
            f"the expected virtual environment {expected_prefix}."
        )
        return ProbeResult.failure(probe_name, message)

    message = (
        f"Python is running from virtual environment "
        f"{actual_prefix} using {executable}."
    )
    return ProbeResult.success(probe_name, message)


def sitecustomize_module_is_active(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the intended sitecustomize module was loaded."""
    probe_name = "python__sitecustomize_module_is_active"
    purelib_path = Path(sysconfig.get_path("purelib"))
    expected_path = purelib_path / "sitecustomize.py"

    if not expected_path.is_file():
        message = f"sitecustomize module is not present at {expected_path}."
        return ProbeResult.failure(probe_name, message)

    sitecustomize_module = sys.modules.get("sitecustomize")
    if sitecustomize_module is None:
        message = "sitecustomize was not loaded during Python startup."
        return ProbeResult.failure(probe_name, message)

    module_file = getattr(sitecustomize_module, "__file__", None)
    if module_file is None:
        message = "Loaded sitecustomize module has no file location."
        return ProbeResult.failure(probe_name, message)

    actual_path = Path(module_file).resolve()
    if actual_path != expected_path.resolve():
        message = f"Expected sitecustomize from {expected_path}, got {actual_path}."
        return ProbeResult.failure(probe_name, message)

    message = f"sitecustomize was loaded from {actual_path}."
    return ProbeResult.success(probe_name, message)


def denied_python_modules_cannot_be_imported(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify denied Python modules cannot be imported."""
    del probe_context

    probe_name = "python__denied_python_modules_cannot_be_imported"
    imported_modules: list[str] = []
    unexpected_errors: list[str] = []

    for module_name in _DENIED_MODULE_NAMES:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        except Exception as error:
            unexpected_errors.append(f"{module_name}: {type(error).__name__}: {error}")
        else:
            imported_modules.append(module_name)

    if imported_modules:
        module_list = ", ".join(imported_modules)
        message = f"Denied Python modules were importable: {module_list}."
        return ProbeResult.failure(probe_name, message)

    if unexpected_errors:
        error_list = "; ".join(unexpected_errors)
        message = f"Denied-module checks produced unexpected errors: {error_list}."
        return ProbeResult.failure(probe_name, message)

    message = "Denied Python modules cannot be imported."
    return ProbeResult.success(probe_name, message)


def ordinary_imports_from_writable_locations_are_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify ordinary imports cannot load code from writable locations."""
    del probe_context

    probe_name = "python__ordinary_imports_from_writable_locations_are_denied"
    imported_paths: list[Path] = []
    unexpected_errors: list[str] = []

    for root in _DENIED_CODE_ROOTS:
        module_name, module_path = _create_probe_module(root, "ordinary_import")
        original_sys_path = sys.path.copy()

        try:
            sys.path.insert(0, str(root))
            importlib.invalidate_caches()

            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError:
                continue
            except Exception as error:
                unexpected_errors.append(
                    f"{module_path}: {type(error).__name__}: {error}"
                )
            else:
                imported_paths.append(module_path)
        finally:
            sys.path[:] = original_sys_path
            sys.modules.pop(module_name, None)
            importlib.invalidate_caches()
            module_path.unlink(missing_ok=True)

    if imported_paths:
        paths = ", ".join(str(path) for path in imported_paths)
        message = f"Python imported code from writable locations: {paths}."
        return ProbeResult.failure(probe_name, message)

    if unexpected_errors:
        errors = "; ".join(unexpected_errors)
        message = f"Writable-location import checks failed unexpectedly: {errors}."
        return ProbeResult.failure(probe_name, message)

    message = "Ordinary imports from writable locations are denied."
    return ProbeResult.success(probe_name, message)


def file_location_imports_from_writable_locations_are_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify file-location imports cannot load code from writable locations."""
    del probe_context

    probe_name = "python__file_location_imports_from_writable_locations_are_denied"
    imported_paths: list[Path] = []
    unexpected_errors: list[str] = []

    for root in _DENIED_CODE_ROOTS:
        module_name, module_path = _create_probe_module(root, "file_import")

        try:
            try:
                module_specification = importlib.util.spec_from_file_location(
                    module_name,
                    module_path,
                )
                if module_specification is None or module_specification.loader is None:
                    message = "Python did not create an executable module specification"
                    raise RuntimeError(message)

                module = importlib.util.module_from_spec(module_specification)
                module_specification.loader.exec_module(module)
            except ModuleNotFoundError:
                continue
            except Exception as error:
                unexpected_errors.append(
                    f"{module_path}: {type(error).__name__}: {error}"
                )
            else:
                imported_paths.append(module_path)
        finally:
            sys.modules.pop(module_name, None)
            module_path.unlink(missing_ok=True)

    if imported_paths:
        paths = ", ".join(str(path) for path in imported_paths)
        message = f"Python loaded code from writable locations: {paths}."
        return ProbeResult.failure(probe_name, message)

    if unexpected_errors:
        errors = "; ".join(unexpected_errors)
        message = f"Writable-location file import checks failed unexpectedly: {errors}."
        return ProbeResult.failure(probe_name, message)

    message = "File-location imports from writable locations are denied."
    return ProbeResult.success(probe_name, message)


def scripts_from_writable_locations_cannot_be_started(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify new Python interpreters reject scripts in writable locations."""
    del probe_context

    probe_name = "python__scripts_from_writable_locations_cannot_be_started"
    executable_paths: list[Path] = []
    unexpected_results: list[str] = []

    for root in _DENIED_CODE_ROOTS:
        _, script_path = _create_probe_module(root, "script")

        try:
            try:
                with permit_process_spawn():
                    completed_process = subprocess.run(
                        [sys.executable, str(script_path)],
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
            except (OSError, subprocess.SubprocessError) as error:
                unexpected_results.append(
                    f"{script_path}: {type(error).__name__}: {error}"
                )
                continue

            if completed_process.returncode == 0:
                executable_paths.append(script_path)
                continue

            if completed_process.returncode != 126:
                unexpected_results.append(
                    f"{script_path}: unexpected exit status "
                    f"{completed_process.returncode}"
                )
        finally:
            script_path.unlink(missing_ok=True)

    if executable_paths:
        paths = ", ".join(str(path) for path in executable_paths)
        message = f"Python executed scripts from writable locations: {paths}."
        return ProbeResult.failure(probe_name, message)

    if unexpected_results:
        results = "; ".join(unexpected_results)
        message = f"Writable-location script checks failed unexpectedly: {results}."
        return ProbeResult.failure(probe_name, message)

    message = "Python scripts in writable locations cannot be started."
    return ProbeResult.success(probe_name, message)


def pip_entry_point_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the pip entry point is unavailable."""
    return _entry_point_is_absent("pip")


def pip3_entry_point_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the pip3 entry point is unavailable."""
    return _entry_point_is_absent("pip3")


def pip_module_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the pip module is unavailable."""
    return _module_is_absent("pip")


def wheel_module_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the wheel module is unavailable."""
    return _module_is_absent("wheel")


def ensurepip_module_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the ensurepip module is unavailable."""
    return _module_is_absent("ensurepip")


def setuptools_module_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the setuptools module is unavailable."""
    return _module_is_absent("setuptools")


def pkg_resources_module_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the pkg_resources module is unavailable."""
    return _module_is_absent("pkg_resources")


def distutils_hack_module_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the _distutils_hack module is unavailable."""
    return _module_is_absent("_distutils_hack")


def package_management_metadata_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify package-management distribution metadata is unavailable."""
    probe_name = "python__package_management_metadata_is_absent"
    distribution_names = ("pip", "setuptools", "wheel")
    installed_distributions: list[str] = []

    for distribution_name in distribution_names:
        try:
            distribution = importlib.metadata.distribution(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            continue

        installed_distributions.append(
            f"{distribution.metadata['Name']} {distribution.version}"
        )

    if installed_distributions:
        distributions = ", ".join(installed_distributions)
        message = f"Package-management metadata found: {distributions}."
        return ProbeResult.failure(probe_name, message)

    message = "Package-management metadata is unavailable."
    return ProbeResult.success(probe_name, message)


PYTHON_PROBES = ProbeGroup(
    name="python",
    probes=(
        metisa_python_virtual_environment_is_active,
        sitecustomize_module_is_active,
        denied_python_modules_cannot_be_imported,
        ordinary_imports_from_writable_locations_are_denied,
        file_location_imports_from_writable_locations_are_denied,
        scripts_from_writable_locations_cannot_be_started,
        pip_entry_point_is_absent,
        pip3_entry_point_is_absent,
        pip_module_is_absent,
        wheel_module_is_absent,
        ensurepip_module_is_absent,
        setuptools_module_is_absent,
        pkg_resources_module_is_absent,
        distutils_hack_module_is_absent,
        package_management_metadata_is_absent,
    ),
)


def _entry_point_is_absent(entry_point_name: str) -> ProbeResult:
    probe_name = f"python__{entry_point_name}_entry_point_is_absent"
    entry_point_paths: set[Path] = set()

    discovered_entry_point = shutil.which(entry_point_name)
    if discovered_entry_point is not None:
        entry_point_paths.add(Path(discovered_entry_point))

    virtual_environment_entry_point = Path(sys.prefix) / "bin" / entry_point_name
    if virtual_environment_entry_point.exists():
        entry_point_paths.add(virtual_environment_entry_point)

    if entry_point_paths:
        paths = ", ".join(str(path) for path in sorted(entry_point_paths))
        message = f"Entry point {entry_point_name} found at: {paths}."
        return ProbeResult.failure(probe_name, message)

    message = f"Entry point {entry_point_name} is unavailable."
    return ProbeResult.success(probe_name, message)


def _module_is_absent(module_name: str) -> ProbeResult:
    probe_name = f"python__{module_name}_module_is_absent"

    try:
        module_specification = importlib.machinery.PathFinder.find_spec(module_name)
    except (ImportError, AttributeError, ValueError) as error:
        message = (
            f"Could not determine whether module {module_name} is installed: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    if module_specification is not None:
        location = module_specification.origin or "unknown location"
        message = f"Module {module_name} is installed at {location}."
        return ProbeResult.failure(probe_name, message)

    message = f"Module {module_name} is not installed."
    return ProbeResult.success(probe_name, message)


def _create_probe_module(root: Path, purpose: str) -> tuple[str, Path]:
    module_name = f"metisa_probe_{purpose}_{uuid.uuid4().hex}"
    module_path = root / f"{module_name}.py"
    module_path.write_text(_PROBE_MODULE_SOURCE, encoding="utf-8")
    return module_name, module_path
