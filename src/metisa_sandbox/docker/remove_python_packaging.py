"""Remove Python packaging modules and associated metadata from the image."""

from __future__ import annotations

import shutil
import sysconfig
from pathlib import Path

_PACKAGE_NAMES = (
    "_distutils_hack",
    "ensurepip",
    "pip",
    "pkg_resources",
    "setuptools",
    "wheel",
)

_METADATA_NAMES = (
    "pip",
    "setuptools",
    "wheel",
)

_LIBRARY_ROOTS = (
    Path("/usr/local/lib"),
    Path("/usr/lib"),
)


def main() -> None:
    """Remove Python packaging modules and metadata."""
    search_paths = _get_python_search_paths()
    patterns = _get_removal_patterns()

    for search_path in search_paths:
        _remove_matches(search_path, patterns)


def _get_python_search_paths() -> set[Path]:
    search_paths: set[Path] = set()

    sysconfig_paths = sysconfig.get_paths()
    for path_name in ("purelib", "platlib", "stdlib", "platstdlib"):
        configured_path = sysconfig_paths.get(path_name)
        if configured_path:
            search_paths.add(Path(configured_path))

    for library_root in _LIBRARY_ROOTS:
        if not library_root.is_dir():
            continue

        search_paths.update(library_root.glob("python*/site-packages"))
        search_paths.update(library_root.glob("python*/dist-packages"))

    return {
        search_path
        for search_path in search_paths
        if search_path.is_dir()
    }


def _get_removal_patterns() -> tuple[str, ...]:
    patterns: list[str] = list(_PACKAGE_NAMES)

    for distribution_name in _METADATA_NAMES:
        normalized_names = {
            distribution_name,
            distribution_name.replace("_", "-"),
        }

        for normalized_name in normalized_names:
            patterns.append(f"{normalized_name}-*.dist-info")
            patterns.append(f"{normalized_name}-*.egg-info")

    patterns.append("distutils-precedence.pth")

    return tuple(patterns)


def _remove_matches(
    search_path: Path,
    patterns: tuple[str, ...],
) -> None:
    for pattern in patterns:
        for match in search_path.glob(pattern):
            _remove_path(match)


def _remove_path(
    path: Path,
) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()