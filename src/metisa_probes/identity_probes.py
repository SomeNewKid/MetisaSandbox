import subprocess

from .models import ProbeContext, ProbeGroup, ProbeResult


def current_user_is_sandbox_user(probe_context: ProbeContext) -> ProbeResult:
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


IDENTITY_PROBES = ProbeGroup(
    name="identity",
    probes=(
        current_user_is_sandbox_user,
    ),
)