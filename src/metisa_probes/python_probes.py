"""Probes related to the Python framework."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import sys
import sysconfig
from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult


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
        module_specification = importlib.util.find_spec(module_name)
    except (ImportError, AttributeError, ValueError) as error:
        message = (
            f"Could not determine whether module {module_name} is available: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    if module_specification is not None:
        location = module_specification.origin or "unknown location"
        message = f"Module {module_name} found at {location}."
        return ProbeResult.failure(probe_name, message)

    message = f"Module {module_name} is unavailable."
    return ProbeResult.success(probe_name, message)
