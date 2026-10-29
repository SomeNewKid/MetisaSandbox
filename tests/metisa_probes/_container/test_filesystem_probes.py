from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from metisa_probes._container import _filesystem_probes as probes
from metisa_probes._probe_models import ProbeContext, ProbeFunction


@pytest.mark.parametrize(
    "probe",
    [
        probes.sandbox_output_volume_is_writable,
        probes.sandbox_work_location_is_writable,
    ],
)
def test_writable_locations_create_and_remove_canary(
    probe_context: ProbeContext, probe: ProbeFunction
) -> None:
    result = probe(probe_context)
    assert result.passed, result.message
    assert not list(Path(probe_context.output_volume).iterdir())
    assert not list(Path(probe_context.work_dir).iterdir())


@pytest.mark.parametrize(
    "probe",
    [
        probes.sandbox_output_volume_is_writable,
        probes.sandbox_work_location_is_writable,
    ],
)
def test_writable_location_rejects_write_error(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, probe: ProbeFunction
) -> None:
    monkeypatch.setattr(
        Path, "write_text", Mock(side_effect=PermissionError("read-only"))
    )
    assert not probe(probe_context).passed


@pytest.mark.parametrize(
    "probe",
    [
        probes.sandbox_source_volume_is_not_writable,
        probes.sandbox_source_module_is_not_writable,
        probes.etc_directory_is_not_writable,
        probes.usr_local_bin_directory_is_not_writable,
    ],
)
@pytest.mark.parametrize("denied", [False, True])
def test_read_only_locations(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    denied: bool,
) -> None:
    write = Mock(side_effect=PermissionError("read-only") if denied else None)
    monkeypatch.setattr(Path, "write_text", write)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    unlink = Mock()
    monkeypatch.setattr(Path, "unlink", unlink)
    assert probe(probe_context).passed is denied
    if not denied:
        unlink.assert_called_once()


@pytest.mark.parametrize(
    "content,passed",
    [("Metisa probes", True), ("", False), ("other", False), (None, False)],
)
def test_source_module_readable(
    probe_context: ProbeContext, content: str | None, passed: bool
) -> None:
    package = Path(probe_context.source_volume) / "metisa_probes"
    package.mkdir()
    if content is not None:
        (package / "__init__.py").write_text(content, encoding="utf-8")
    assert probes.sandbox_source_module_file_is_readable(probe_context).passed is passed


@pytest.mark.parametrize(
    "probe,entry,directory",
    [
        (probes.source_control_metadata_is_absent, ".git", True),
        (probes.source_control_metadata_is_absent, ".git", False),
        (probes.development_directories_are_absent, "tests", True),
        (probes.development_directories_are_absent, ".pytest_cache", True),
        (probes.host_sandbox_module_is_absent, "metisa_sandbox", True),
        (probes.generated_python_artifacts_are_absent, "__pycache__", True),
        (probes.generated_python_artifacts_are_absent, "package.dist-info", True),
        (probes.generated_python_artifacts_are_absent, "package.egg-info", True),
        (probes.project_configuration_files_are_absent, "pyproject.toml", False),
        (probes.project_configuration_files_are_absent, "requirements.txt", False),
    ],
)
def test_staged_source_excludes_nested_artifacts(
    probe_context: ProbeContext, probe: ProbeFunction, entry: str, directory: bool
) -> None:
    source = Path(probe_context.source_volume)
    assert probe(probe_context).passed
    nested = source / "nested"
    nested.mkdir()
    target = nested / entry
    if directory:
        target.mkdir()
    else:
        target.write_text("artifact", encoding="utf-8")
    result = probe(probe_context)
    assert not result.passed
    assert entry in result.message


@pytest.mark.parametrize(
    "probe",
    [
        probes.source_control_metadata_is_absent,
        probes.development_directories_are_absent,
        probes.host_sandbox_module_is_absent,
        probes.generated_python_artifacts_are_absent,
        probes.project_configuration_files_are_absent,
    ],
)
@pytest.mark.parametrize("mode", ["missing", "unreadable"])
def test_source_inspection_failure(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    mode: str,
) -> None:
    monkeypatch.setattr(Path, "is_dir", lambda self: mode != "missing")
    monkeypatch.setattr(Path, "rglob", Mock(side_effect=OSError("cannot enumerate")))
    assert not probe(probe_context).passed


@pytest.mark.parametrize(
    "probe",
    [
        probes.sandbox_home_directory_is_not_writable,
        probes.effective_home_directory_is_not_writable,
        probes.effective_xdg_config_directory_is_not_writable,
        probes.effective_xdg_cache_directory_is_not_writable,
    ],
)
@pytest.mark.parametrize("denied", [False, True])
def test_home_and_xdg_write_policy(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    tmp_path: Path,
    probe: ProbeFunction,
    denied: bool,
) -> None:
    monkeypatch.setattr(probes, "_get_sandbox_home_directory", lambda: tmp_path)
    monkeypatch.setattr(probes.os, "environ", {})
    monkeypatch.setattr(
        Path,
        "write_text",
        Mock(side_effect=PermissionError("policy") if denied else None),
    )
    monkeypatch.setattr(Path, "unlink", Mock())
    result = probe(probe_context)
    assert result.passed is denied, result.message
    # Missing .config/.cache children must still test their existing parent.
    assert str(tmp_path) in result.message


def test_home_redirection_fails(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, tmp_path: Path
) -> None:
    monkeypatch.setattr(probes, "_get_sandbox_home_directory", lambda: tmp_path)
    monkeypatch.setattr(probes.os, "environ", {"HOME": str(tmp_path / "redirect")})
    assert not probes.effective_home_directory_is_not_writable(probe_context).passed


@pytest.mark.parametrize(
    "probe,variable",
    [
        (probes.effective_xdg_config_directory_is_not_writable, "XDG_CONFIG_HOME"),
        (probes.effective_xdg_cache_directory_is_not_writable, "XDG_CACHE_HOME"),
    ],
)
def test_relative_xdg_directory_fails(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    variable: str,
) -> None:
    monkeypatch.setattr(probes.os, "environ", {variable: "relative"})
    assert not probe(probe_context).passed


@pytest.mark.parametrize("present", [False, True])
def test_runtime_directory_environment(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, present: bool
) -> None:
    monkeypatch.setattr(
        probes.os, "environ", {"XDG_RUNTIME_DIR": ""} if present else {}
    )
    assert (
        probes.effective_xdg_runtime_directory_is_absent(probe_context).passed
        is not present
    )


@pytest.mark.parametrize("exists", [False, True])
def test_work_location_exists(
    monkeypatch: pytest.MonkeyPatch, probe_context: ProbeContext, exists: bool
) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: exists)
    assert probes.sandbox_work_location_is_available(probe_context).passed is exists


@pytest.mark.parametrize(
    "mountinfo,passed",
    [
        ("1 0 0:1 / / ro,relatime - overlay overlay rw", True),
        ("1 0 0:1 / / rw - overlay overlay rw", False),
        ("1 0 0:1 / /other ro - tmpfs tmpfs ro", False),
        ("bad", False),
        ("", False),
    ],
)
def test_root_mount(
    read_text: Mock, probe_context: ProbeContext, mountinfo: str, passed: bool
) -> None:
    read_text.return_value = mountinfo
    assert probes.root_filesystem_is_read_only(probe_context).passed is passed


@pytest.mark.parametrize(
    "probe,mount,size",
    [
        (probes.tmp_directory_is_hardened_tmpfs, "/tmp", 16 * 1024 * 1024),
        (probes.sandbox_work_location_is_hardened_tmpfs, None, 1024 * 1024),
    ],
)
@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "wrong_fs",
        "missing_option",
        "wrong_size",
        "write_error",
        "missing",
        "malformed",
    ],
)
def test_tmpfs_hardening(
    monkeypatch: pytest.MonkeyPatch,
    read_text: Mock,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    mount: str | None,
    size: int,
    mode: str,
) -> None:
    mount = str(Path(mount or probe_context.work_dir))
    options = (
        "rw,nosuid,nodev" if mode == "missing_option" else "rw,nosuid,nodev,noexec"
    )
    filesystem = "ext4" if mode == "wrong_fs" else "tmpfs"
    read_text.return_value = f"1 0 0:1 / {mount} {options} - {filesystem} tmpfs rw"
    if mode == "missing":
        read_text.return_value = ""
    elif mode == "malformed":
        read_text.return_value = "bad"
    monkeypatch.setattr(
        probes.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=size + 1 if mode == "wrong_size" else size),
    )
    monkeypatch.setattr(
        Path,
        "write_text",
        Mock(side_effect=PermissionError("policy") if mode == "write_error" else None),
    )
    monkeypatch.setattr(Path, "unlink", Mock())
    result = probe(probe_context)
    assert result.passed is (mode == "valid"), result.message


@pytest.mark.parametrize(
    "probe", [probes.proc_acpi_is_concealed, probes.sys_firmware_is_concealed]
)
@pytest.mark.parametrize(
    "mode", ["concealed", "missing", "exposed", "writable", "unreadable"]
)
def test_concealed_system_paths(
    monkeypatch: pytest.MonkeyPatch,
    probe_context: ProbeContext,
    probe: ProbeFunction,
    mode: str,
) -> None:
    monkeypatch.setattr(Path, "is_dir", lambda self: mode != "missing")
    entries = Mock(return_value=iter([Path("device")] if mode == "exposed" else []))
    if mode == "unreadable":
        entries.side_effect = OSError("cannot inspect")
    monkeypatch.setattr(Path, "iterdir", entries)
    monkeypatch.setattr(
        Path,
        "write_text",
        Mock(side_effect=None if mode == "writable" else PermissionError("denied")),
    )
    monkeypatch.setattr(Path, "unlink", Mock())
    assert probe(probe_context).passed is (mode == "concealed")
