"""Probes related to Python process creation."""

from __future__ import annotations

import importlib
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from typing import cast

from .models import ProbeContext, ProbeGroup, ProbeResult
from .probe_helpers import permit_process_spawn

_CHILD_ARGUMENTS = (sys.executable, "-c", "pass")

_EXEC_FUNCTION_NAMES = (
    "execl",
    "execle",
    "execlp",
    "execlpe",
    "execv",
    "execve",
    "execvp",
    "execvpe",
)

_EXEC_PROBE_CODE = """
import os
import sys

function_name = sys.argv[1]
function = vars(os)[function_name]
executable = sys.executable
target_code = "raise SystemExit(73)"
arguments = (
    executable,
    "-I",
    "-B",
    "-c",
    target_code,
)

os.environ["METISA_RUNTIME_ROLE"] = "workload"
environment = os.environ.copy()

try:
    if function_name in {"execl", "execlp"}:
        function(executable, *arguments)
    elif function_name in {"execle", "execlpe"}:
        function(executable, *arguments, environment)
    elif function_name in {"execv", "execvp"}:
        function(executable, arguments)
    else:
        function(executable, arguments, environment)
except PermissionError:
    raise SystemExit(0)
except Exception as error:
    print(f"{type(error).__name__}: {error}", file=sys.stderr)
    raise SystemExit(74)

raise SystemExit(75)
"""


def subprocess_popen_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify subprocess.Popen cannot create a child process."""
    del probe_context
    return _process_operation_is_denied(
        "process__subprocess_popen_is_denied",
        "subprocess.Popen",
        _start_with_subprocess_popen,
    )


def subprocess_run_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify subprocess.run cannot create a child process."""
    del probe_context
    return _process_operation_is_denied(
        "process__subprocess_run_is_denied",
        "subprocess.run",
        lambda: subprocess.run(_CHILD_ARGUMENTS, check=False),
    )


def subprocess_call_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify subprocess.call cannot create a child process."""
    del probe_context
    return _process_operation_is_denied(
        "process__subprocess_call_is_denied",
        "subprocess.call",
        lambda: subprocess.call(_CHILD_ARGUMENTS),
    )


def subprocess_check_call_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify subprocess.check_call cannot create a child process."""
    del probe_context
    return _process_operation_is_denied(
        "process__subprocess_check_call_is_denied",
        "subprocess.check_call",
        lambda: subprocess.check_call(_CHILD_ARGUMENTS),
    )


def subprocess_check_output_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify subprocess.check_output cannot create a child process."""
    del probe_context
    return _process_operation_is_denied(
        "process__subprocess_check_output_is_denied",
        "subprocess.check_output",
        lambda: subprocess.check_output(_CHILD_ARGUMENTS),
    )


def os_system_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify os.system cannot create a shell process."""
    del probe_context
    return _process_operation_is_denied(
        "process__os_system_is_denied",
        "os.system",
        lambda: os.system(_child_command_text()),
    )


def os_popen_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify os.popen cannot create a shell process."""
    del probe_context
    return _process_operation_is_denied(
        "process__os_popen_is_denied",
        "os.popen",
        _start_with_os_popen,
    )


def os_spawn_family_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify available os.spawn family functions cannot create processes."""
    del probe_context

    probe_name = "process__os_spawn_family_is_denied"
    operations = _get_spawn_operations()
    allowed_functions: list[str] = []
    unexpected_errors: list[str] = []

    for function_name, operation in operations:
        try:
            operation()
        except PermissionError:
            continue
        except Exception as error:
            unexpected_errors.append(
                f"{function_name}: {type(error).__name__}: {error}"
            )
        else:
            allowed_functions.append(function_name)

    if allowed_functions:
        functions = ", ".join(allowed_functions)
        message = f"Process creation was allowed through: {functions}."
        return ProbeResult.failure(probe_name, message)

    if unexpected_errors:
        errors = "; ".join(unexpected_errors)
        message = f"Spawn-family checks failed unexpectedly: {errors}."
        return ProbeResult.failure(probe_name, message)

    message = "Process creation through the available os.spawn family is denied."
    return ProbeResult.success(probe_name, message)


def pty_spawn_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify pty.spawn cannot create a child process."""
    del probe_context
    return _process_operation_is_denied(
        "process__pty_spawn_is_denied",
        "pty.spawn",
        _start_with_pty_spawn,
    )


def os_exec_family_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the os.exec family cannot replace the workload process."""
    del probe_context

    probe_name = "process__os_exec_family_is_denied"
    allowed_functions: list[str] = []
    unexpected_results: list[str] = []

    environment = os.environ.copy()
    environment["METISA_RUNTIME_ROLE"] = "workload"

    for function_name in _EXEC_FUNCTION_NAMES:
        if not callable(vars(os).get(function_name)):
            unexpected_results.append(f"os.{function_name}: unavailable")
            continue

        try:
            with permit_process_spawn():
                completed_process = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        "-c", 
                        _EXEC_PROBE_CODE, 
                        function_name],
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
        except Exception as error:
            unexpected_results.append(
                f"os.{function_name}: {type(error).__name__}: {error}"
            )
            continue

        if completed_process.returncode == 0:
            continue

        if completed_process.returncode == 73:
            allowed_functions.append(f"os.{function_name}")
            continue

        stderr = completed_process.stderr.strip()
        detail = stderr or "no error output"
        unexpected_results.append(
            f"os.{function_name}: exit status {completed_process.returncode}: {detail}"
        )

    if allowed_functions:
        functions = ", ".join(allowed_functions)
        message = f"Process replacement was allowed through: {functions}."
        return ProbeResult.failure(probe_name, message)

    if unexpected_results:
        results = "; ".join(unexpected_results)
        message = f"Exec-family checks failed unexpectedly: {results}."
        return ProbeResult.failure(probe_name, message)

    message = "Process replacement through the os.exec family is denied."
    return ProbeResult.success(probe_name, message)


def os_fork_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify os.fork cannot create a child process."""
    del probe_context
    return _process_operation_is_denied(
        "process__os_fork_is_denied",
        "os.fork",
        _start_with_os_fork,
    )


def os_forkpty_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify os.forkpty cannot create a child process."""
    del probe_context
    return _process_operation_is_denied(
        "process__os_forkpty_is_denied",
        "os.forkpty",
        _start_with_os_forkpty,
    )


def os_posix_spawn_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify os.posix_spawn cannot create a child process."""
    del probe_context
    return _process_operation_is_denied(
        "process__os_posix_spawn_is_denied",
        "os.posix_spawn",
        _start_with_os_posix_spawn,
    )


def os_posix_spawnp_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify os.posix_spawnp cannot create a child process."""
    del probe_context
    return _process_operation_is_denied(
        "process__os_posix_spawnp_is_denied",
        "os.posix_spawnp",
        _start_with_os_posix_spawnp,
    )


PROCESS_PROBES = ProbeGroup(
    name="process",
    probes=(
        subprocess_popen_is_denied,
        subprocess_run_is_denied,
        subprocess_call_is_denied,
        subprocess_check_call_is_denied,
        subprocess_check_output_is_denied,
        os_system_is_denied,
        os_popen_is_denied,
        os_spawn_family_is_denied,
        pty_spawn_is_denied,
        os_exec_family_is_denied,
        os_fork_is_denied,
        os_forkpty_is_denied,
        os_posix_spawn_is_denied,
        os_posix_spawnp_is_denied,
    ),
)


def _process_operation_is_denied(
    probe_name: str,
    operation_name: str,
    operation: Callable[[], object],
) -> ProbeResult:
    try:
        operation()
    except PermissionError:
        message = f"Process creation through {operation_name} is denied."
        return ProbeResult.success(probe_name, message)
    except Exception as error:
        message = (
            f"{operation_name} failed unexpectedly: {type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    message = f"Process creation through {operation_name} was allowed."
    return ProbeResult.failure(probe_name, message)


def _start_with_subprocess_popen() -> None:
    child_process = subprocess.Popen(_CHILD_ARGUMENTS)
    child_process.wait(timeout=5)


def _child_command_text() -> str:
    executable = shlex.quote(sys.executable)
    return f"{executable} -c pass"


def _start_with_os_popen() -> None:
    with os.popen(_child_command_text()) as child_output:
        child_output.read()


def _get_spawn_operations() -> tuple[tuple[str, Callable[[], object]], ...]:
    environment = os.environ.copy()
    executable = sys.executable
    arguments = (executable, "-c", "pass")
    operations: list[tuple[str, Callable[[], object]]] = []

    if hasattr(os, "spawnl"):
        operations.append(
            ("os.spawnl", lambda: os.spawnl(os.P_WAIT, executable, *arguments))
        )
    if hasattr(os, "spawnle"):
        operations.append(
            (
                "os.spawnle",
                lambda: os.spawnle(os.P_WAIT, executable, *arguments, environment),
            )
        )
    spawnlp = vars(os).get("spawnlp")
    if callable(spawnlp):
        operations.append(
            ("os.spawnlp", lambda: spawnlp(os.P_WAIT, executable, *arguments))
        )
    spawnlpe = vars(os).get("spawnlpe")
    if callable(spawnlpe):
        operations.append(
            (
                "os.spawnlpe",
                lambda: spawnlpe(os.P_WAIT, executable, *arguments, environment),
            )
        )
    if hasattr(os, "spawnv"):
        operations.append(
            ("os.spawnv", lambda: os.spawnv(os.P_WAIT, executable, arguments))
        )
    if hasattr(os, "spawnve"):
        operations.append(
            (
                "os.spawnve",
                lambda: os.spawnve(os.P_WAIT, executable, arguments, environment),
            )
        )
    spawnvp = vars(os).get("spawnvp")
    if callable(spawnvp):
        operations.append(
            ("os.spawnvp", lambda: spawnvp(os.P_WAIT, executable, arguments))
        )
    spawnvpe = vars(os).get("spawnvpe")
    if callable(spawnvpe):
        operations.append(
            (
                "os.spawnvpe",
                lambda: spawnvpe(os.P_WAIT, executable, arguments, environment),
            )
        )

    return tuple(operations)


def _start_with_pty_spawn() -> None:
    pty = importlib.import_module("pty")
    pty.spawn(_CHILD_ARGUMENTS)


def _start_with_os_fork() -> None:
    fork_candidate = vars(os).get("fork")
    if not callable(fork_candidate):
        raise RuntimeError("os.fork is unavailable")

    fork = cast(Callable[[], int], fork_candidate)
    child_process_id = fork()
    if child_process_id == 0:
        os._exit(0)

    os.waitpid(child_process_id, 0)


def _start_with_os_forkpty() -> None:
    forkpty_candidate = vars(os).get("forkpty")
    if not callable(forkpty_candidate):
        raise RuntimeError("os.forkpty is unavailable")

    forkpty = cast(Callable[[], tuple[int, int]], forkpty_candidate)
    child_process_id, file_descriptor = forkpty()
    if child_process_id == 0:
        os._exit(0)

    os.close(file_descriptor)
    os.waitpid(child_process_id, 0)


def _start_with_os_posix_spawn() -> None:
    posix_spawn_candidate = vars(os).get("posix_spawn")
    if not callable(posix_spawn_candidate):
        raise RuntimeError("os.posix_spawn is unavailable")

    posix_spawn = cast(Callable[..., int], posix_spawn_candidate)
    child_process_id = posix_spawn(
        sys.executable,
        _CHILD_ARGUMENTS,
        os.environ.copy(),
    )
    os.waitpid(child_process_id, 0)


def _start_with_os_posix_spawnp() -> None:
    posix_spawnp_candidate = vars(os).get("posix_spawnp")
    if not callable(posix_spawnp_candidate):
        raise RuntimeError("os.posix_spawnp is unavailable")

    posix_spawnp = cast(Callable[..., int], posix_spawnp_candidate)
    child_process_id = posix_spawnp(
        sys.executable,
        _CHILD_ARGUMENTS,
        os.environ.copy(),
    )
    os.waitpid(child_process_id, 0)
