"""Probes related to the user identity."""

import subprocess
from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult


def current_user_is_sandbox_user(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the probes are running as the sandbox user."""
    probe_name = "identity__current_user_is_sandbox_user"

    result = subprocess.run(
        ["id", "--user", "--name"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        return ProbeResult.failure(probe_name, message)

    user_name = result.stdout.strip()
    if user_name != "sandbox":
        message = f"Expected user sandbox, got {user_name}."
        return ProbeResult.failure(probe_name, message)

    return ProbeResult.success(probe_name, "Current user is sandbox.")


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
