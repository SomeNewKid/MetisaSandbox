"""Probes related to Docker."""

from __future__ import annotations

import socket
from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult


def docker_socket_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """
    Ensure Docker socket is absent.

    Mounting the Docker socket would effectively
    let the workload control the host Docker daemon.
    """
    probe_name = "docker__docker_socket_is_absent"
    socket_file = Path("/var/run/docker.sock")
    if socket_file.exists():
        return ProbeResult.failure(probe_name, f"File exists at {socket_file}")
    else:
        return ProbeResult.success(probe_name, f"File does not exist at {socket_file}")


def docker_host_paths_are_absent(probe_context: ProbeContext) -> ProbeResult:
    """
    Ensure Docker host paths are absent
    """
    probe_name = "docker__docker_host_paths_are_absent"

    host_dir = Path("/host")
    if host_dir.exists():
        return ProbeResult.failure(probe_name, f"Directory exists at {host_dir}")

    mnt_c_dir = Path("/mnt/c")
    if mnt_c_dir.exists():
        return ProbeResult.failure(probe_name, f"Directory exists at {mnt_c_dir}")

    message = f"Directories do not exist at {host_dir} or {mnt_c_dir}"
    return ProbeResult.success(probe_name, message)


def docker_container_runtime_is_detected(probe_context: ProbeContext) -> ProbeResult:
    """
    Verifies the probes are running inside a container runtime.
    """
    probe_name = "docker__docker_container_runtime_is_detected"

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


def _read_text_if_available(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _contains_container_runtime_marker(text: str) -> bool:
    markers = (
        "docker",
        "containerd",
        "kubepods",
        "podman",
    )
    text_lowered = text.lower()
    return any(marker in text_lowered for marker in markers)


def _looks_like_container_hostname(hostname: str) -> bool:
    if len(hostname) != 12:
        return False

    hostname_lowered = hostname.lower()
    return all(character in "0123456789abcdef" for character in hostname_lowered)


DOCKER_PROBES = ProbeGroup(
    name="docker",
    probes=(
        docker_socket_is_absent,
        docker_host_paths_are_absent,
        docker_container_runtime_is_detected,
    ),
)
