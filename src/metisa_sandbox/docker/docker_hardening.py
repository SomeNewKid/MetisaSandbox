"""Provides utility methods for Docker container hardening."""

from __future__ import annotations

from pathlib import Path

HARDENING_LABEL = "hardened=true"


def harden_docker_container(
    arguments: list[str],
    environs: list[str],
    username: str,
    *,
    read_only: bool = True,
    interactive: bool = False,
    cpu_count: int | None = 1,
    memory: str = "128m",
    number_container_processes: int = 64,
    file_size_limit: int | None = 1048576,
    number_of_files: int | None = 256,
    number_user_processes: int | None = None,
    seccomp_path: Path | None = None,
    health_start_seconds: int = 60,
) -> None:
    """Add arguments to hardenen the container."""
    if not username:
        raise ValueError("Username is required.")

    # Mount the container's root filesystem as strictly read-only
    # Couple with in memory temporary writes (--tmpfs)
    # or with read-write mounted volumes (-volume /host/path:/volume:rw).
    if read_only:
        arguments.extend(
            [
                "--read-only",
            ]
        )

    # Linux control groups, or cgroups, organize processes and
    # enforce resource accounting and limits such as:
    # - Memory usage
    # - CPU allocation
    # - Process counts
    # - I/O limits
    # Docker already places each container into one or more cgroups.
    # A cgroup namespace controls how much of that cgroup hierarchy a process can see.
    arguments.extend(
        [
            "--cgroupns",
            "private",
        ]
    )

    # Run as a custom user, if image has no native non-root user.
    uid, gid = _get_uid_gid(username)
    if uid is not None and gid is not None:
        arguments.extend(
            ["--user", f"{uid}:{gid}"],
        )

    # Executing another program cannot grant the process privileges
    # it did not already have.  It prevents privilege escalation through:
    # Set-user-ID,
    # Set-group-ID,
    # Executables with Linux file capabilities.
    arguments.extend(
        [
            "--security-opt",
            "no-new-privileges=true",
        ]
    )

    # Allocate a pseudo-terminal.
    # Allows Python `input` to get user input from the terminal.
    if interactive:
        arguments.extend(
            [
                "--interactive",  # keeps stdin open
                "--tty",  # allocates a pseudo-terminal
            ]
        )

    # Drop all Linux capabilities for the container.
    # https://man7.org/linux/man-pages/man7/capabilities.7.html
    # Docker already excludes more dangerous capabilities such as
    # SYS_ADMIN, NET_ADMIN, SYS_PTRACE, and SYS_MODULE by default.
    arguments.extend(["--cap-drop", "ALL"])

    # Set CPU limits for the container.
    if cpu_count is not None and cpu_count > 0:
        arguments.extend(
            [
                "--cpus",
                str(cpu_count),
            ]
        )

    # Set memory limits for the container.
    arguments.extend(
        [
            "--memory",
            memory,
            "--memory-swap",  # no additional swap beyond the memory limit
            memory,
        ]
    )

    # Set the open file descriptor limits for the container.
    # A file descriptor is a small non-negative integer that
    # a Unix process uses as a handle to an open operating-system resource.
    # Limiting descriptors protects against accidental or hostile resource exhaustion.
    if number_of_files is not None:
        arguments.extend(
            [
                "--ulimit",
                f"nofile={number_of_files}:{number_of_files}",
            ]
        )

    # Without --init, the command supplied after the image
    # becomes PID 1 inside the container.
    # PID 1 has special responsibilities on Linux.
    # In particular, it inherits orphaned descendant processes and
    # must collect, or “reap,” processes that have exited.
    # Ordinary applications are not always designed to perform that role correctly.
    # With --init, Docker inserts its small docker-init process as PID 1.
    arguments.extend(
        [
            "--init",  # correctly reaps exited and orphaned processes.
            "--pids-limit",  # Bounds how many processes the container may have at once
            str(number_container_processes),
        ]
    )

    # Set the per-user process limits for the container.
    # Disabled by default, because this limit applies to the UID/GID user,
    # which may be shared across mutliple containers and leads to
    # thread exhaustion in containers.
    # The preceding `pids-limit` limits the total number of processes in the container.
    if number_user_processes is not None and number_user_processes > 0:
        arguments.extend(
            [
                "--ulimit",
                f"nproc={number_user_processes}:{number_user_processes}",
            ]
        )

    # Set the file size limits for the container.
    # (Applies to file writes, not to existing files.)
    if file_size_limit is not None:
        arguments.extend(
            [
                "--ulimit",
                f"fsize={file_size_limit}:{file_size_limit}",
            ]
        )

    # Require privileges when binding ports below 1024.
    arguments.extend(
        [
            "--sysctl",
            "net.ipv4.ip_unprivileged_port_start=1024",
        ]
    )

    # Apply the Seccomp file.
    if seccomp_path is not None:
        if not seccomp_path.is_file():
            raise ValueError(f"Seccomp profile not found at {seccomp_path}")
        arguments.extend(["--security-opt", f"seccomp={seccomp_path}"])

    # Set the environment variables.
    for environ in environs:
        arguments.extend(
            [
                "--env",
                environ,
            ]
        )

    # Allow the container more time to start.
    # The model is loaded eagerly, which can take some time.
    arguments.extend(
        [
            "--health-start-period",
            f"{health_start_seconds}s",
        ]
    )

    arguments.extend(
        [
            "--label",
            HARDENING_LABEL,
        ]
    )


def configure_http_proxy(
    environs: list[str],
    squid_proxy_url: str | None,
) -> None:
    """Add HTTP proxy environment variables."""
    if not squid_proxy_url:
        return
    no_proxy_destinations = ",".join(
        [
            "localhost",
            "127.0.0.1",
            "::1",
            "metisa-workload",
            "metisa-squid",
            "metisa-mcp-server",
            "metisa-llm-broker",
        ]
    )
    environs.extend(
        [
            f"HTTP_PROXY={squid_proxy_url}",
            f"HTTPS_PROXY={squid_proxy_url}",
            f"NO_PROXY={no_proxy_destinations}",
            f"http_proxy={squid_proxy_url}",
            f"https_proxy={squid_proxy_url}",
            f"no_proxy={no_proxy_destinations}",
        ]
    )


def _get_uid_gid(
    username: str,
) -> tuple[int | None, int | None]:
    match username:
        case "sandbox":
            return (10001, 10001)
        case "squid":
            return (None, None)  # (10002, 10002) Squid Proxy provides non-root user
        case "haproxy":
            return (None, None)  # (10003, 10003) HAProxy provides non-root user
        case "warden":
            return (10004, 10004)
        case "broker":
            return (10005, 10005)
        case "coder":
            return (10006, 10006)
        case "librarian":
            return (10007, 10007)
        case "guardian":
            return (10008, 10008)
        case "surfer":
            return (None, None)  # (10009, 10009) Jina Reader provides non-root user
        case "llama":
            return (None, None)  # (10010, 10010) Llama.pp provides non-root user
        case _:
            raise ValueError(f"Unknown username: {username}")
