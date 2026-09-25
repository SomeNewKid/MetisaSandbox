"""Customize Python in the hardened Docker container.

A sitecustomize.py file is a special script that automatically executes
every time the Python interpreter starts up.
It is a built-in configuration hook provided by Python's core site module
to allow system administrators or tools to perform global,
environment-wide customizations before any other user script runs.
"""

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import ipaddress
import os
import pty
import socket
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, NoReturn

_STARTUP_CONFIGURATION_ERROR = 78

_VALID_RUNTIME_ROLES = frozenset(
    {
        "landlock",
        "runner",
        "probes",
        "workload",
    }
) 

_RUNTIME_ROLE = os.environ.pop("METISA_RUNTIME_ROLE", "")

_ORIGINAL_SOCKET = socket.socket
_ORIGINAL_SPEC_FROM_FILE_LOCATION = importlib.util.spec_from_file_location
_ORIGINAL_SUBPROCESS_RUN = subprocess.run
_ORIGINAL_SUBPROCESS_POPEN = subprocess.Popen
_ORIGINAL_PATH_EXISTS = Path.exists
_ORIGINAL_PATH_GLOB = Path.glob
_ORIGINAL_PATH_ITERDIR = Path.iterdir

_BLOCKED_HOSTNAMES = frozenset({"metadata.google.internal"})
_BLOCKED_IP_ADDRESSES = frozenset(
    {
        ipaddress.ip_address("fd00:ec2::254"),
        ipaddress.ip_address("fd20:ce::254"),
    }
)
_IPV4_LINK_LOCAL_NETWORK = ipaddress.ip_network("169.254.0.0/16")
_IPV6_LINK_LOCAL_NETWORK = ipaddress.ip_network("fe80::/10")

_DENIED_IMPORT_MODULES = frozenset(
    {
        "_ctypes",
        "ctypes",
        "ensurepip",
        "pip",
        "setuptools",
        "wheel",
    }
)
_DENIED_CODE_ROOTS = tuple(
    Path(path).resolve(strict=False)
    for path in (
        "/sandbox-output",
        "/sandbox-work",
        "/tmp",
    )
)

_DENIED_HARDWARE_COMMAND_MARKERS = frozenset(
    {
        "/dev/snd",
        "/sys/bus/usb",
        "/sys/class/bluetooth",
        "arecord",
        "bluetoothctl",
        "lpstat",
        "lsusb",
        "ttyACM",
        "ttyS",
        "ttyUSB",
        "video*",
        "video4linux2",
    }
)
_DENIED_HARDWARE_GLOBS = frozenset({"video*", "ttyS*", "ttyUSB*", "ttyACM*"})

_ALLOWED_RUNNER_PROCESS_SPAWN_MARKERS = frozenset(
    {
        "/opt/metisa-venv/bin/python -I -B -m metisa_probes",
    }
)
_ALLOWED_WORKLOAD_PROCESS_SPAWN_MARKERS = frozenset(
    {
        "/ms-playwright/",
        "/playwright/driver/",
    }
)

_PROBE_SPAWN_PERMITTED = ContextVar(
    "metisa_probe_spawn_permitted",
    default=False,
)


@contextmanager
def permit_probe_process_spawn() -> Generator[None, None, None]:
    """Temporarily permit trusted probe-harness process creation."""
    if _RUNTIME_ROLE != "probes":
        raise PermissionError(
            "Probe process-spawn scope is unavailable outside probe execution."
        )

    token = _PROBE_SPAWN_PERMITTED.set(True)

    try:
        yield
    finally:
        _PROBE_SPAWN_PERMITTED.reset(token)


def _terminate_startup(message: str) -> NoReturn:
    """Report an invalid runtime configuration and terminal immediately."""
    output = f"Metisa Python startup rejected: {message}\n"

    try:
        os.write(
            2,
            output.encode("utf-8", errors="replace"),
        )
    finally:
        # ensures termination even if standard error is unavailable 
        # or writing to it fails. 
        # os._exit() deliberately skips ordinary exception handling, 
        # flushing, and cleanup; 
        # that is appropriate here because the interpreter has 
        # not completed trusted initialization and must not continue.
        os._exit(_STARTUP_CONFIGURATION_ERROR)


def _validate_role() -> None:
    if _RUNTIME_ROLE not in _VALID_RUNTIME_ROLES:
        _terminate_startup("Invalid or missing Metisa runtime role")


def _ensure_isolated_mode() -> None:
    if not sys.flags.isolated:
        _terminate_startup("Python isolated mode is not enabled")

    if not sys.flags.safe_path:
        _terminate_startup("Python safe-path mode is not enabled")

    if not sys.flags.no_user_site:
        _terminate_startup("Python user site-packages are enabled")


def _deny_potentially_dangerous_module_imports() -> None:
    """Apply defense-in-depth restrictions to Python module use.

    The guard prevents importing certain sensitive or potentially dangerous
    Python modules.
    """

    class _DeniedModuleFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):  # type: ignore[no-untyped-def]
            module_name = fullname.partition(".")[0]

            if module_name in _DENIED_IMPORT_MODULES:
                message = f"{fullname!r} is denied by sandbox profile."
                raise ModuleNotFoundError(message)

            return None

    sys.meta_path.insert(0, _DeniedModuleFinder())


def _deny_code_imports_from_writable_locations() -> None:
    """Deny ordinary imports whose resolved source is in writable storage."""

    class _DeniedCodeFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):  # type: ignore[no-untyped-def]
            module_specification = importlib.machinery.PathFinder.find_spec(
                fullname,
                path,
                target,
            )
            if module_specification is None:
                return None

            origin = module_specification.origin
            if origin is None or origin in {"built-in", "frozen"}:
                return None

            if _path_is_under_denied_code_root(origin):
                message = (
                    f"Importing {fullname!r} from writable path "
                    f"{origin!r} is denied by sandbox profile."
                )
                raise ModuleNotFoundError(message)

            return None

    sys.meta_path.insert(0, _DeniedCodeFinder())


def _deny_writable_spec_from_file_location() -> None:
    """Deny file-location imports from writable locations."""

    def guarded_spec_from_file_location(name, location, *args, **kwargs):  # type: ignore[no-untyped-def]
        if _path_is_under_denied_code_root(location):
            message = (
                f"Importing {name!r} from writable path {location!r} "
                "is denied by sandbox profile."
            )
            raise ModuleNotFoundError(message)

        return _ORIGINAL_SPEC_FROM_FILE_LOCATION(name, location, *args, **kwargs)

    importlib.util.spec_from_file_location = guarded_spec_from_file_location


def _deny_writable_script_execution() -> None:
    """Deny direct Python script execution from writable locations."""
    script_path = _get_script_path()
    if script_path is None:
        return

    if not _path_is_under_denied_code_root(script_path):
        return

    os.write(
        2,
        (
            f"Python script execution from writable path {script_path}"
            "is denied by sandbox profile.\n"
        ).encode("utf-8", errors="replace"),
    )
    os._exit(126)


def _apply_hardware_device_guards() -> None:
    """Apply defense-in-depth restrictions to hardware device access."""

    def guarded_subprocess_run(args, *run_args, **run_kwargs):  # type: ignore[no-untyped-def]
        if _is_denied_hardware_command(args):
            raise PermissionError(
                "Hardware device enumeration is denied by sandbox profile."
            )

        return _ORIGINAL_SUBPROCESS_RUN(args, *run_args, **run_kwargs)

    def guarded_path_exists(self: Path) -> bool:
        if _is_denied_hardware_path(self):
            raise PermissionError(
                "Hardware device enumeration is denied by sandbox profile."
            )

        return _ORIGINAL_PATH_EXISTS(self)

    def guarded_path_glob(self: Path, pattern: str):  # type: ignore[no-untyped-def]
        if _is_denied_hardware_glob(self, pattern):
            raise PermissionError(
                "Hardware device enumeration is denied by sandbox profile"
            )

        return _ORIGINAL_PATH_GLOB(self, pattern)

    def guarded_path_iterdir(self: Path):  # type: ignore[no-untyped-def]
        if _is_denied_hardware_path(self):
            raise PermissionError(
                "Hardware device enumeration is denied by sandbox profile"
            )

        return _ORIGINAL_PATH_ITERDIR(self)

    subprocess.run = guarded_subprocess_run
    Path.exists = guarded_path_exists  # type: ignore[method-assign]
    Path.glob = guarded_path_glob  # type: ignore[method-assign]
    Path.iterdir = guarded_path_iterdir  # type: ignore[method-assign]


def _apply_process_spawn_guards() -> None:
    """Apply defense-in-depth restrictions to process spawning."""

    class GuardedPopen(_ORIGINAL_SUBPROCESS_POPEN):  # type: ignore[misc]
        def __init__(self, args, *popen_args, **popen_kwargs):  # type: ignore[no-untyped-def]
            _raise_if_process_spawn_denied(args)
            super().__init__(args, *popen_args, **popen_kwargs)

    def guarded_run(args, *run_args, **run_kwargs):  # type: ignore[no-untyped-def]
        _raise_if_process_spawn_denied(args)
        return _ORIGINAL_SUBPROCESS_RUN(args, *run_args, **run_kwargs)

    def denied_os_system(command: object) -> int:
        raise PermissionError("Process spawning is denied by sandbox profile")

    def denied_os_popen(command, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise PermissionError("Process spawning is denied by sandbox profile")

    def denied_spawn(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise PermissionError("Process spawning is denied by sandbox profile")

    subprocess.Popen = GuardedPopen
    subprocess.run = guarded_run
    subprocess.call = guarded_run
    subprocess.check_call = guarded_run
    subprocess.check_output = guarded_run
    os.system = denied_os_system
    os.popen = denied_os_popen
    os.spawnl = denied_os_popen
    os.spawnle = denied_os_popen

    disallowed_os_spawn_functions = [
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execve",
        "execvp",
        "execvpe",
        "fork",
        "forkpty",
        "posix_spawn",
        "posix_spawnp",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
    ]
    if _RUNTIME_ROLE not in ("landlock", "runner"):
        disallowed_os_spawn_functions.append(
            "execv",
        )

    for name in disallowed_os_spawn_functions:
        if hasattr(os, name):
            setattr(os, name, denied_spawn)

    if hasattr(pty, "spawn"):
        pty.spawn = denied_spawn  # type: ignore[attr-defined]


def _apply_socket_guards() -> None:
    """Apply defense-in-depth restrictions to Python socket operations.

    The guard rejects creation of IPv4 and IPv6 UDP sockets.
    The guard rejects binding IPv4 and IPv6 sockets to all local interfaces.
    The guard rejects link-local or known cloud-metadata destinations passed
    directly through its guarded connection methods.

    These restrictions apply only to Python code using the patched
    `socket.socket` class.  They supplement, but do not replace,
    Docker network isolation or operating-system-level network controls.
    """

    class GuardedSocket(_ORIGINAL_SOCKET):
        def __init__(
            self,
            family: int = socket.AF_INET,
            type: int = socket.SOCK_STREAM,
            proto: int = 0,
            fileno: int | None = None,
        ) -> None:
            """Create a socket unless its family and type are prohibited."""
            socket_type = type & 0x0F

            if (
                family in (socket.AF_INET, socket.AF_INET6)
                and socket_type == socket.SOCK_DGRAM
            ):
                raise PermissionError("IPv4 and IPv6 UDP sockets are disabled.")

            super().__init__(family, type, proto, fileno)

        def bind(self, address: Any) -> None:
            """Reject IPv4 and IPv6 binds to all interfaces."""
            if self.family in (socket.AF_INET, socket.AF_INET6):
                host = address[0]

                if host == "" or host == b"":
                    raise PermissionError(
                        "Binding to all network interfaces is disabled."
                    )

                normalized_host = host

                if isinstance(host, bytes):
                    try:
                        normalized_host = host.decode("ascii")
                    except UnicodeDecodeError:
                        normalized_host = host

                try:
                    ip_address = ipaddress.ip_address(normalized_host)
                except (TypeError, ValueError):
                    ip_address = None

                if ip_address is not None and ip_address.is_unspecified:
                    raise PermissionError(
                        "Binding to all network interfaces is disabled."
                    )

            super().bind(address)

        def connect(self, address: Any) -> None:
            """Reject connections to prohibited IPv4, IPv6, and named hosts."""
            self._reject_blocked_destination(address)
            super().connect(address)

        def connect_ex(self, address: Any) -> int:
            """Reject prohibited destinations before returning a connection status."""
            self._reject_blocked_destination(address)
            return super().connect_ex(address)

        def _reject_blocked_destination(self, address: Any) -> None:
            if self.family not in (socket.AF_INET, socket.AF_INET6):
                return

            host = _normalize_host(address[0])

            if host is None:
                return

            hostname = host.rstrip(".").lower()

            if hostname in _BLOCKED_HOSTNAMES:
                raise PermissionError(f"Connections to {host!r} are disabled.")

            address_text = host.split("%", maxsplit=1)[0]

            try:
                ip_address = ipaddress.ip_address(address_text)
            except ValueError:
                return

            comparable_address = ip_address

            if isinstance(ip_address, ipaddress.IPv6Address):
                ipv4_address = ip_address.ipv4_mapped

                if ipv4_address is not None:
                    comparable_address = ipv4_address

            if (
                comparable_address in _IPV4_LINK_LOCAL_NETWORK
                or comparable_address in _IPV6_LINK_LOCAL_NETWORK
                or ip_address in _BLOCKED_IP_ADDRESSES
            ):
                raise PermissionError(f"Connections to {host!r} are disabled.")

    def _normalize_host(host: Any) -> str | None:
        if isinstance(host, str):
            return host

        if isinstance(host, bytes):
            try:
                return host.decode("ascii")
            except UnicodeDecodeError:
                return None

        return None

    socket.socket = GuardedSocket


def _path_is_under_denied_code_root(path: object) -> bool:
    path_text = _path_text(path)
    if not path_text:
        return False

    try:
        resolved_path = Path(path_text).resolve(strict=False)
    except OSError:
        return False

    return any(_is_relative_to(resolved_path, root) for root in _DENIED_CODE_ROOTS)


def _path_text(path: object) -> str | None:
    if not isinstance(path, (str, os.PathLike)):
        return None

    return os.fspath(path)


def _command_text(args: object) -> str:
    if isinstance(args, (str, bytes, os.PathLike)):
        return os.fsdecode(args)

    if not isinstance(args, (list, tuple)):
        return ""

    return " ".join(os.fsdecode(item) for item in args)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False

    return True


def _get_script_path() -> Path | None:
    if not sys.argv:
        return None

    script_name = sys.argv[0]
    if not script_name or script_name in {"-c", "-m"}:
        return None

    script_path = Path(script_name)
    if not script_path.is_absolute():
        script_path = Path.cwd() / script_path

    return script_path.resolve(strict=False)


def _is_denied_hardware_command(args: object) -> bool:
    text = _command_text(args)
    if not text:
        return False

    return any(marker in text for marker in _DENIED_HARDWARE_COMMAND_MARKERS)


def _is_denied_hardware_path(path: object) -> bool:
    path_text = _path_text(path)

    if not path_text:
        return False

    denied_hardware_paths = (
        value for value in _DENIED_HARDWARE_COMMAND_MARKERS if value.startswith("/")
    )

    return path_text in denied_hardware_paths


def _is_denied_hardware_glob(path: object, pattern: object) -> bool:
    path_text = _path_text(path)
    pattern_text = _path_text(pattern)
    if path_text != "/dev":
        return False

    return pattern_text in _DENIED_HARDWARE_GLOBS


def _raise_if_process_spawn_denied(args: object) -> None:
    if _is_allowed_process_spawn(args):
        return

    raise PermissionError("Process spawning is denied by sandbox profile")


def _is_allowed_process_spawn(args: object) -> bool:
    if _RUNTIME_ROLE == "runner":
        return _is_allowed_runner_command(args)

    if _RUNTIME_ROLE == "probes":
        return _PROBE_SPAWN_PERMITTED.get()

    if _RUNTIME_ROLE == "workload":
        return _is_allowed_workload_command(args)

    return False


def _is_allowed_runner_command(args: object) -> bool:
    return _is_allowed_command(args, _ALLOWED_RUNNER_PROCESS_SPAWN_MARKERS)


def _is_allowed_workload_command(args: object) -> bool:
    return _is_allowed_command(args, _ALLOWED_WORKLOAD_PROCESS_SPAWN_MARKERS)


def _is_allowed_command(args: object, allowed_markers: frozenset[str]) -> bool:
    text = _command_text(args)
    if not text:
        return False

    normalized_text = text.replace("\\", "/")

    return any(normalized_text.startswith(marker) for marker in allowed_markers)


_validate_role()
_ensure_isolated_mode()
_apply_socket_guards()
_deny_potentially_dangerous_module_imports()
_deny_code_imports_from_writable_locations()
_deny_writable_spec_from_file_location()
_deny_writable_script_execution()
_apply_hardware_device_guards()
_apply_process_spawn_guards()
