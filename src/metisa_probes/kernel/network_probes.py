"""Probes related to kernel networking policy."""

from pathlib import Path

from ..models import ProbeContext, ProbeGroup, ProbeResult


def unprivileged_port_start_is_1024(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify ports below 1024 require a privileged process."""
    probe_name = "kernel__network__unprivileged_port_start_is_1024"
    expected_port = 1024
    sysctl_path = Path("/proc/sys/net/ipv4/ip_unprivileged_port_start")

    try:
        raw_port = sysctl_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        message = f"Could not read {sysctl_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    try:
        actual_port = int(raw_port)
    except ValueError:
        message = f"Invalid unprivileged port start {raw_port!r} at {sysctl_path}."
        return ProbeResult.failure(probe_name, message)

    if actual_port != expected_port:
        message = (
            f"Expected unprivileged ports to start at {expected_port}, "
            f"got {actual_port}."
        )
        return ProbeResult.failure(probe_name, message)

    message = f"Unprivileged ports start at {actual_port}."
    return ProbeResult.success(probe_name, message)


KERNEL_NETWORK_PROBES = ProbeGroup(
    name="kernel_network",
    probes=(unprivileged_port_start_is_1024,),
)
