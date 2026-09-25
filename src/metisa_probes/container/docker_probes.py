"""Probes related to Docker."""

from __future__ import annotations

import os
import socket
import stat
from pathlib import Path

from ..models import ProbeContext, ProbeGroup, ProbeResult


def docker_socket_is_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """
    Ensure Docker socket is absent.

    Mounting the Docker socket would effectively
    let the workload control the host Docker daemon.
    """
    probe_name = "container__docker__docker_socket_is_absent"
    socket_file = Path("/var/run/docker.sock")
    if socket_file.exists():
        return ProbeResult.failure(probe_name, f"File exists at {socket_file}")
    else:
        return ProbeResult.success(probe_name, f"File does not exist at {socket_file}")


def docker_host_paths_are_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Ensure Docker host paths are absent."""
    probe_name = "container__docker__docker_host_paths_are_absent"

    host_dir = Path("/host")
    if host_dir.exists():
        return ProbeResult.failure(probe_name, f"Directory exists at {host_dir}")

    mnt_c_dir = Path("/mnt/c")
    if mnt_c_dir.exists():
        return ProbeResult.failure(probe_name, f"Directory exists at {mnt_c_dir}")

    message = f"Directories do not exist at {host_dir} or {mnt_c_dir}"
    return ProbeResult.success(probe_name, message)


def docker_container_runtime_is_detected(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify the probes are running inside a container runtime."""
    probe_name = "container__docker__docker_container_runtime_is_detected"

    evidence = []

    dockerenv_path = Path("./dockerenv")
    if dockerenv_path.exists():
        evidence.append(f"{dockerenv_path} exists")

    cgroup_path = Path("/proc/1/cgroup")
    cgroup_text = _read_text_if_available(cgroup_path)
    if _contains_container_runtime_marker(cgroup_text):
        evidence.append(f"{cgroup_path} contains container runtime marker")

    mountinfo_path = Path("/proc/self/mountinfo")
    mountinfo_text = _read_text_if_available(mountinfo_path)
    if _contains_container_runtime_marker(mountinfo_text):
        evidence.append(f"{mountinfo_path} contains container runtime marker")

    hostname = socket.gethostname()
    if _looks_like_container_hostname(hostname):
        evidence.append(f"hostname looks container-like: {hostname}")

    if evidence:
        success_message = "; ".join(evidence)
        return ProbeResult.success(probe_name, success_message)

    failure_message = "No Docker/container runtime evidence was found."
    return ProbeResult.failure(probe_name, failure_message)


def cgroup_namespace_is_private(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify cgroup paths are rooted in the container's namespace."""
    probe_name = "container__docker__cgroup_namespace_is_private"
    cgroup_path = Path("/proc/self/cgroup")

    try:
        cgroup_text = cgroup_path.read_text(encoding="utf-8")
    except OSError as error:
        message = f"Could not read {cgroup_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    cgroup_lines = [line for line in cgroup_text.splitlines() if line]
    if not cgroup_lines:
        message = f"No cgroup entries were found in {cgroup_path}."
        return ProbeResult.failure(probe_name, message)

    visible_paths: set[str] = set()

    for line in cgroup_lines:
        fields = line.split(":", maxsplit=2)
        if len(fields) != 3:
            message = f"Malformed cgroup entry in {cgroup_path}: {line!r}."
            return ProbeResult.failure(probe_name, message)

        visible_paths.add(fields[2])

    unexpected_paths = sorted(path for path in visible_paths if path != "/")
    if unexpected_paths:
        paths = ", ".join(unexpected_paths)
        message = f"Cgroup paths are visible outside the namespace root: {paths}."
        return ProbeResult.failure(probe_name, message)

    message = "All visible cgroup paths are rooted at /."
    return ProbeResult.success(probe_name, message)


def init_process_is_enabled(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Docker's init process is running as PID 1."""
    probe_name = "container__docker__init_process_is_enabled"
    process_name_path = Path("/proc/1/comm")

    try:
        process_name = process_name_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        message = f"Could not read {process_name_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    if process_name != "docker-init":
        message = f"Expected PID 1 to be docker-init, got {process_name!r}."
        return ProbeResult.failure(probe_name, message)

    message = "Docker init process is running as PID 1."
    return ProbeResult.success(probe_name, message)


def host_socket_mounts_are_absent(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify no Unix sockets are mounted into the container."""
    probe_name = "container__docker__host_socket_mounts_are_absent"
    mountinfo_path = Path("/proc/self/mountinfo")

    try:
        mountinfo = mountinfo_path.read_text(encoding="utf-8")
    except OSError as error:
        message = f"Could not read {mountinfo_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    socket_mounts: list[Path] = []

    for line in mountinfo.splitlines():
        mount_fields = line.partition(" - ")[0].split()
        if len(mount_fields) < 5:
            message = f"Malformed mount entry in {mountinfo_path}: {line!r}."
            return ProbeResult.failure(probe_name, message)

        mount_point = Path(_decode_mountinfo_path(mount_fields[4]))

        try:
            mount_mode = mount_point.stat().st_mode
        except OSError as error:
            message = (
                f"Could not inspect mount point {mount_point}: "
                f"{type(error).__name__}: {error}"
            )
            return ProbeResult.failure(probe_name, message)

        if stat.S_ISSOCK(mount_mode):
            socket_mounts.append(mount_point)

    if socket_mounts:
        paths = ", ".join(str(path) for path in sorted(socket_mounts))
        message = f"Unix sockets are mounted at: {paths}."
        return ProbeResult.failure(probe_name, message)

    message = "No Unix sockets are mounted into the container."
    return ProbeResult.success(probe_name, message)


def ssh_agent_is_unavailable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify no SSH-agent endpoint is configured."""
    probe_name = "container__docker__ssh_agent_is_unavailable"
    environment_variable = "SSH_AUTH_SOCK"

    if environment_variable in os.environ:
        configured_value = os.environ[environment_variable]
        message = (
            f"SSH-agent environment variable {environment_variable} is configured "
            f"as {configured_value!r}."
        )
        return ProbeResult.failure(probe_name, message)

    message = f"SSH-agent environment variable {environment_variable} is absent."
    return ProbeResult.success(probe_name, message)


def gpg_agent_is_unavailable(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify no GPG-agent endpoint is configured or active."""
    probe_name = "container__docker__gpg_agent_is_unavailable"
    environment_variable = "GPG_AGENT_INFO"

    if environment_variable in os.environ:
        configured_value = os.environ[environment_variable]
        message = (
            f"GPG-agent environment variable {environment_variable} is configured "
            f"as {configured_value!r}."
        )
        return ProbeResult.failure(probe_name, message)

    unix_socket_path = Path("/proc/net/unix")

    try:
        unix_sockets = unix_socket_path.read_text(encoding="utf-8")
    except OSError as error:
        message = f"Could not read {unix_socket_path}: {type(error).__name__}: {error}"
        return ProbeResult.failure(probe_name, message)

    gpg_agent_sockets = sorted(
        {
            fields[-1]
            for line in unix_sockets.splitlines()
            if "S.gpg-agent" in line
            if (fields := line.split())
        }
    )

    if gpg_agent_sockets:
        paths = ", ".join(gpg_agent_sockets)
        message = f"GPG-agent Unix sockets are active at: {paths}."
        return ProbeResult.failure(probe_name, message)

    message = "No GPG-agent endpoint is configured or active."
    return ProbeResult.success(probe_name, message)


def _read_text_if_available(
    path: Path,
) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _contains_container_runtime_marker(
    text: str,
) -> bool:
    markers = (
        "docker",
        "containerd",
        "kubepods",
        "podman",
    )
    text_lowered = text.lower()
    return any(marker in text_lowered for marker in markers)


def _looks_like_container_hostname(
    hostname: str,
) -> bool:
    if len(hostname) != 12:
        return False

    hostname_lowered = hostname.lower()
    return all(character in "0123456789abcdef" for character in hostname_lowered)


def _decode_mountinfo_path(encoded_path: str) -> str:
    return (
        encoded_path.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
    )


DOCKER_PROBES = ProbeGroup(
    name="docker",
    probes=(
        docker_socket_is_absent,
        docker_host_paths_are_absent,
        docker_container_runtime_is_detected,
        cgroup_namespace_is_private,
        init_process_is_enabled,
        host_socket_mounts_are_absent,
        ssh_agent_is_unavailable,
        gpg_agent_is_unavailable,
    ),
)
