"""Probes related to the user identity."""

import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

from .models import ProbeContext, ProbeGroup, ProbeResult


def current_user_is_sandbox_user(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the probes are running as the sandbox user."""
    del probe_context

    probe_name = "identity__current_user_is_sandbox_user"
    passwd_path = Path("/etc/passwd")

    get_effective_user_id_candidate = vars(os).get("geteuid")
    if not callable(get_effective_user_id_candidate):
        message = "The operating system does not provide os.geteuid()."
        return ProbeResult.failure(probe_name, message)

    get_effective_user_id = cast(
        Callable[[], int],
        get_effective_user_id_candidate,
    )
    effective_user_id = get_effective_user_id()

    try:
        passwd_contents = passwd_path.read_text(encoding="utf-8")
    except OSError as error:
        message = f"Could not read {passwd_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    sandbox_user_ids: list[int] = []

    for line in passwd_contents.splitlines():
        fields = line.split(":")
        if len(fields) != 7 or fields[0] != "sandbox":
            continue

        try:
            sandbox_user_ids.append(int(fields[2]))
        except ValueError:
            message = f"The sandbox account has an invalid UID: {fields[2]!r}."
            return ProbeResult.failure(probe_name, message)

    if not sandbox_user_ids:
        message = "The sandbox account was not found in /etc/passwd."
        return ProbeResult.failure(probe_name, message)

    if len(sandbox_user_ids) > 1:
        message = "Multiple sandbox account entries were found in /etc/passwd."
        return ProbeResult.failure(probe_name, message)

    sandbox_user_id = sandbox_user_ids[0]
    if effective_user_id != sandbox_user_id:
        message = (
            f"Expected effective UID {sandbox_user_id} for sandbox, "
            f"got {effective_user_id}."
        )
        return ProbeResult.failure(probe_name, message)

    message = f"Effective UID {effective_user_id} belongs to sandbox."
    return ProbeResult.success(probe_name, message)


def sandbox_user_login_shell_is_nologin(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the sandbox account uses the nologin shell."""
    probe_name = "identity__sandbox_user_login_shell_is_nologin"
    passwd_path = Path("/etc/passwd")
    expected_shell = "/usr/sbin/nologin"

    try:
        passwd_contents = passwd_path.read_text(encoding="utf-8")
    except OSError as error:
        message = f"Could not read {passwd_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    matching_entries = []

    for line in passwd_contents.splitlines():
        fields = line.split(":")

        if len(fields) == 7 and fields[0] == "sandbox":
            matching_entries.append(fields)

    if not matching_entries:
        return ProbeResult.failure(
            probe_name,
            "The sandbox account was not found in /etc/passwd.",
        )

    if len(matching_entries) > 1:
        return ProbeResult.failure(
            probe_name,
            "Multiple sandbox account entries were found in /etc/passwd.",
        )

    actual_shell = matching_entries[0][6]

    if actual_shell != expected_shell:
        message = (
            f"Expected sandbox login shell {expected_shell}, "
            f"got {actual_shell or '<empty>'}."
        )
        return ProbeResult.failure(probe_name, message)

    return ProbeResult.success(
        probe_name,
        f"Sandbox login shell is {expected_shell}.",
    )


IDENTITY_PROBES = ProbeGroup(
    name="identity",
    probes=(
        current_user_is_sandbox_user,
        sandbox_user_login_shell_is_nologin,
    ),
)
