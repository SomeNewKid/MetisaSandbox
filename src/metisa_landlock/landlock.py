"""Implement the initial Metisa Landlock policy."""
# Landlock is a Linux Security Module which lets an unprivileged process
# import a kernel-enforced filesystem access policy on itself and its descendants.

from __future__ import annotations

import ctypes
import os
import platform
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from metisa_common.models import MetisaSpecification


class _LandlockPermission(StrEnum):
    READ_FILE = "read_file"
    READ_DIRECTORY = "read_directory"
    WRITE_FILE = "write_file"
    MODIFY_DIRECTORY = "modify_directory"
    EXECUTE = "execute"


_LANDLOCK_ACCESS_FS_EXECUTE = 1 << 0
_LANDLOCK_ACCESS_FS_WRITE_FILE = 1 << 1
_LANDLOCK_ACCESS_FS_READ_FILE = 1 << 2
_LANDLOCK_ACCESS_FS_READ_DIR = 1 << 3
_LANDLOCK_ACCESS_FS_REMOVE_DIR = 1 << 4
_LANDLOCK_ACCESS_FS_REMOVE_FILE = 1 << 5
_LANDLOCK_ACCESS_FS_MAKE_CHAR = 1 << 6
_LANDLOCK_ACCESS_FS_MAKE_DIR = 1 << 7
_LANDLOCK_ACCESS_FS_MAKE_REG = 1 << 8
_LANDLOCK_ACCESS_FS_MAKE_SOCK = 1 << 9
_LANDLOCK_ACCESS_FS_MAKE_FIFO = 1 << 10
_LANDLOCK_ACCESS_FS_MAKE_BLOCK = 1 << 11
_LANDLOCK_ACCESS_FS_MAKE_SYM = 1 << 12
_LANDLOCK_ACCESS_FS_REFER = 1 << 13
_LANDLOCK_ACCESS_FS_TRUNCATE = 1 << 14

_READ_FILE_RIGHTS = _LANDLOCK_ACCESS_FS_READ_FILE

_READ_DIRECTORY_RIGHTS = _LANDLOCK_ACCESS_FS_READ_DIR

_BASE_WRITE_FILE_RIGHTS = _LANDLOCK_ACCESS_FS_WRITE_FILE

_BASE_MODIFY_DIRECTORY_RIGHTS = (
    _LANDLOCK_ACCESS_FS_REMOVE_DIR
    | _LANDLOCK_ACCESS_FS_REMOVE_FILE
    | _LANDLOCK_ACCESS_FS_MAKE_CHAR
    | _LANDLOCK_ACCESS_FS_MAKE_DIR
    | _LANDLOCK_ACCESS_FS_MAKE_REG
    | _LANDLOCK_ACCESS_FS_MAKE_SOCK
    | _LANDLOCK_ACCESS_FS_MAKE_FIFO
    | _LANDLOCK_ACCESS_FS_MAKE_BLOCK
    | _LANDLOCK_ACCESS_FS_MAKE_SYM
)

_EXECUTE_RIGHTS = _LANDLOCK_ACCESS_FS_EXECUTE

_LANDLOCK_RULE_PATH_BENEATH = 1


# Linux syscall numbers used by x86-64 and AArch64.
@dataclass(frozen=True)
class _LandlockSyscalls:
    create_ruleset: int
    add_rule: int
    restrict_self: int


_LANDLOCK_SYSCALLS_BY_ARCHITECTURE = {
    "x86_64": _LandlockSyscalls(
        create_ruleset=444,
        add_rule=445,
        restrict_self=446,
    ),
    "aarch64": _LandlockSyscalls(
        create_ruleset=444,
        add_rule=445,
        restrict_self=446,
    ),
}

_LANDLOCK_CREATE_RULESET_VERSION = 1
_PR_SET_NO_NEW_PRIVS = 38

_REQUIRED_LANDLOCK_ABI = 1


@dataclass
class _LandlockRule:
    path: Path
    permissions: frozenset[_LandlockPermission]


_LANDLOCK_RULES: tuple[_LandlockRule, ...] = (
    _LandlockRule(
        Path("/bin"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
                _LandlockPermission.EXECUTE,
            }
        ),
    ),
    _LandlockRule(
        Path("/etc"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
            }
        ),
    ),
    _LandlockRule(
        Path("/lib"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
                _LandlockPermission.EXECUTE,
            }
        ),
    ),
    _LandlockRule(
        Path("/opt/metisa-venv"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
                _LandlockPermission.EXECUTE,
            }
        ),
    ),
    _LandlockRule(
        Path("/usr"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
                _LandlockPermission.EXECUTE,
            }
        ),
    ),
    _LandlockRule(
        Path("/proc"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
            }
        ),
    ),
    _LandlockRule(
        Path("/sandbox-source"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
            }
        ),
    ),
    _LandlockRule(
        Path("/sandbox-output"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
                _LandlockPermission.WRITE_FILE,
                _LandlockPermission.MODIFY_DIRECTORY,
            }
        ),
    ),
    _LandlockRule(
        Path("/sandbox-work"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
                _LandlockPermission.WRITE_FILE,
                _LandlockPermission.MODIFY_DIRECTORY,
            }
        ),
    ),
    _LandlockRule(
        Path("/tmp"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
                _LandlockPermission.WRITE_FILE,
                _LandlockPermission.MODIFY_DIRECTORY,
            }
        ),
    ),
    _LandlockRule(
        Path("/sys/firmware"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
            }
        ),
    ),
    _LandlockRule(
        Path("/sys/fs/cgroup"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
            }
        ),
    ),
    _LandlockRule(
        Path("/dev"),
        frozenset(
            {
                _LandlockPermission.READ_FILE,
                _LandlockPermission.READ_DIRECTORY,
            }
        ),
    ),
    _LandlockRule(
        Path("/dev/null"),
        frozenset(
            {
                _LandlockPermission.WRITE_FILE,
            }
        ),
    ),
)


class _LandlockRulesetAttribute(ctypes.Structure):
    _fields_ = [
        ("handled_access_fs", ctypes.c_uint64),
    ]


class _LandlockPathBeneathAttribute(ctypes.Structure):
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]


def apply_landlock_rules(
    specification: MetisaSpecification,
    log_file_path: Path,
):
    """Apply the Landlock security rules to the current process."""
    del specification

    if sys.platform != "linux":
        raise RuntimeError("Landlock requires Linux.")

    syscalls = _get_landlock_syscalls()

    libc = ctypes.CDLL(None, use_errno=True)

    abi_version = _get_abi_version(
        libc,
        syscalls,
    )
    (ruleset_fd, ruleset_message) = _create_ruleset(libc, syscalls, abi_version)

    try:
        for landlock_rule in _LANDLOCK_RULES:
            _add_path_rule(libc, syscalls, abi_version, ruleset_fd, landlock_rule)

        _restrict_current_process(libc, syscalls, ruleset_fd)
    finally:
        os.close(ruleset_fd)

    with log_file_path.open("w", encoding="utf-8") as log_file:
        log_file.write(ruleset_message)
        for landlock_rule in _LANDLOCK_RULES:
            permissions = sorted(landlock_rule.permissions)
            permissions_text = ", ".join(permissions)
            log_file.write(f"{landlock_rule.path}: {permissions_text}\n")


def _get_landlock_syscalls() -> _LandlockSyscalls:
    architecture = platform.machine().lower()

    aliases = {
        "amd64": "x86_64",
        "arm64": "aarch64",
    }
    architecture = aliases.get(architecture, architecture)

    syscalls = _LANDLOCK_SYSCALLS_BY_ARCHITECTURE.get(architecture)
    if syscalls is None:
        supported = ", ".join(sorted(_LANDLOCK_SYSCALLS_BY_ARCHITECTURE))
        message = (
            f"Unsupported Linux architecture {architecture!r}; "
            f"Landlock syscall numbers are defined only for: {supported}"
        )
        raise RuntimeError(message)

    return syscalls


def _get_abi_version(
    libc: ctypes.CDLL,
    syscalls: _LandlockSyscalls,
) -> int:
    abi_version = libc.syscall(
        syscalls.create_ruleset,
        None,
        0,
        _LANDLOCK_CREATE_RULESET_VERSION,
    )
    _raise_for_failed_system_call(
        abi_version, "Could not determine the Landlock ABI version"
    )

    if abi_version < _REQUIRED_LANDLOCK_ABI:
        message = (
            f"Landlock ABI {_REQUIRED_LANDLOCK_ABI} or newer is required, "
            f"kernel provides ABI {abi_version}."
        )
        raise RuntimeError(message)

    return abi_version


def _create_ruleset(
    libc: ctypes.CDLL,
    syscalls: _LandlockSyscalls,
    abi_version: int,
) -> tuple[int, str]:

    write_file_rights = _get_write_file_rights(abi_version)
    modify_directory_rights = _get_modify_directory_rights(abi_version)

    handled_access = (
        _READ_FILE_RIGHTS
        | _READ_DIRECTORY_RIGHTS
        | write_file_rights
        | modify_directory_rights
        | _EXECUTE_RIGHTS
    )

    attributes = _LandlockRulesetAttribute(handled_access_fs=handled_access)

    ruleset_fd = libc.syscall(
        syscalls.create_ruleset,
        ctypes.byref(attributes),
        ctypes.sizeof(attributes),
        0,
    )
    _raise_for_failed_system_call(ruleset_fd, "Could not create the Landlock ruleset")

    unsupported_write_rights = []
    if not (write_file_rights & _LANDLOCK_ACCESS_FS_TRUNCATE):
        unsupported_write_rights.append("truncate")
    if not (modify_directory_rights & _LANDLOCK_ACCESS_FS_REFER):
        unsupported_write_rights.append("refer")
    message = f"Landlock ABI: {abi_version}\n"
    if unsupported_write_rights:
        message += f"{', '.join(unsupported_write_rights)}\n"

    return (int(ruleset_fd), message)


def _restrict_current_process(
    libc: ctypes.CDLL,
    syscalls: _LandlockSyscalls,
    ruleset_fd: int,
) -> None:
    no_new_privileges_result = libc.prctl(
        _PR_SET_NO_NEW_PRIVS,
        1,
        0,
        0,
        0,
    )
    _raise_for_failed_system_call(
        no_new_privileges_result,
        "Could not set no_new_privs",
    )

    restriction_result = libc.syscall(
        syscalls.restrict_self,
        ruleset_fd,
        0,
    )
    _raise_for_failed_system_call(
        restriction_result,
        "Could not enforce the Landlock ruleset",
    )


def _add_path_rule(
    libc: ctypes.CDLL,
    syscalls: _LandlockSyscalls,
    abi_version: int,
    ruleset_fd: int,
    rule: _LandlockRule,
) -> None:
    open_flags = _get_linux_open_flag("O_PATH") | _get_linux_open_flag("O_CLOEXEC")

    path_fd = os.open(
        rule.path,
        open_flags,
    )

    try:
        attributes = _LandlockPathBeneathAttribute(
            allowed_access=_create_permissions(rule.permissions, abi_version),
            parent_fd=path_fd,
        )

        result = libc.syscall(
            syscalls.add_rule,
            ruleset_fd,
            _LANDLOCK_RULE_PATH_BENEATH,
            ctypes.byref(attributes),
            0,
        )

        if result == -1:
            error_number = ctypes.get_errno()
            raise OSError(error_number, os.strerror(error_number), rule.path)

    finally:
        os.close(path_fd)


def _create_permissions(
    permissions: frozenset[_LandlockPermission],
    abi_version: int,
) -> int:
    # Convert the list of permission strings to
    # the corresponding Landlock permission bits
    permission_rights = {
        _LandlockPermission.READ_FILE: _READ_FILE_RIGHTS,
        _LandlockPermission.READ_DIRECTORY: _READ_DIRECTORY_RIGHTS,
        _LandlockPermission.WRITE_FILE: _get_write_file_rights(abi_version),
        _LandlockPermission.MODIFY_DIRECTORY: _get_modify_directory_rights(abi_version),
        _LandlockPermission.EXECUTE: _EXECUTE_RIGHTS,
    }

    permission_bits = 0
    for permission in permissions:
        permission_bits |= permission_rights[permission]
    return permission_bits


def _get_write_file_rights(abi_version: int) -> int:
    write_rights = _BASE_WRITE_FILE_RIGHTS

    if abi_version >= 3:
        write_rights |= _LANDLOCK_ACCESS_FS_TRUNCATE

    return write_rights


def _get_modify_directory_rights(abi_version: int) -> int:
    write_rights = _BASE_MODIFY_DIRECTORY_RIGHTS

    if abi_version >= 2:
        write_rights |= _LANDLOCK_ACCESS_FS_REFER

    return write_rights


def _get_linux_open_flag(flag_name: str) -> int:
    flag = getattr(os, flag_name, None)
    if not isinstance(flag, int):
        message = f"Required Linux open flag {flag_name} is unavailable."
        raise RuntimeError(message)
    return flag


def _raise_for_failed_system_call(
    result: int,
    operation: str,
) -> None:
    if result != -1:
        return

    error_number = ctypes.get_errno()
    error_message = os.strerror(error_number)
    raise OSError(error_number, f"{operation}: {error_message}")
