"""Manage a Squid Proxy sidecar."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from metisa_common.specification_helper import generate_image_tag
from metisa_common.specification_models import MetisaSpecification

from ..docker.docker_container import (
    create_docker_container,
    inspect_docker_container,
    start_docker_container,
)
from ..docker.docker_image import (
    build_docker_image,
    docker_image_exists,
)
from ..docker.docker_network import (
    connect_container_to_docker_network,
)
from ..sandbox_context import SandboxContext

_IMAGE_FORMAT_VERSION = 1
_SQUID_PROXY_ALIAS = "metisa-squid"
_SQUID_PROXY_PORT = 3128
_SQUID_PROXY_IMAGE_NAME = "metisa-squid-proxy"


def create_squid_proxy_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
) -> str:
    """Create the Squid Proxy container and connect it to the Docker networks."""
    image_name = _ensure_squid_proxy_image_exists(specification)
    container_name = _create_squid_proxy_container_name(sandbox_context.run_identifier)

    arguments = [
        "--name",
        container_name,
        "--network",
        sandbox_context.egress_network_name,
    ]

    # Mount the container's root filesystem as strictly read-only
    # Couple with in memory temporary writes (--tmpfs)
    # or with read-write mounted volumes (-volume /host/path:/volume:rw).
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

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/tmp:rw,size=16m,nosuid,nodev,noexec",
        ]
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

    # Drop all Linux capabilities for the container.
    # https://man7.org/linux/man-pages/man7/capabilities.7.html
    # Docker already excludes more dangerous capabilities such as
    # SYS_ADMIN, NET_ADMIN, SYS_PTRACE, and SYS_MODULE by default.
    arguments.extend(["--cap-drop", "ALL"])

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
            "64",
        ]
    )

    # Set CPU limits for the container.
    arguments.extend(
        [
            "--cpus",
            "1",
        ]
    )

    # Set memory limits for the container.
    arguments.extend(
        [
            "--memory",
            "128m",
            "--memory-swap",  # no additional swap beyond the memory limit
            "128m",
        ]
    )

    # Set the open file descriptor limits for the container.
    # A file descriptor is a small non-negative integer that
    # a Unix process uses as a handle to an open operating-system resource.
    # Limiting descriptors protects against accidental or hostile resource exhaustion.
    arguments.extend(
        [
            "--ulimit",
            "nofile=256:256",
        ]
    )

    # Set the per-user process limits for the container.
    arguments.extend(
        [
            "--ulimit",
            "nproc=64:64",
        ]
    )

    # Set the file size limits for the container.
    arguments.extend(
        [
            "--ulimit",
            "fsize=1048576:1048576",
        ]
    )

    # Require privileges when binding ports below 1024.
    arguments.extend(
        [
            "--sysctl",
            "net.ipv4.ip_unprivileged_port_start=1024",
        ]
    )

    # The image name must be specified last in the arguments list.
    arguments.extend(
        [
            image_name,
        ]
    )
    create_docker_container(arguments)

    connect_container_to_docker_network(
        container_name=container_name,
        network_name=sandbox_context.private_network_name,
        aliases=(_SQUID_PROXY_ALIAS,),
    )

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("Squid Proxy sidecar failed to start.")

    return container_name


def get_squid_proxy_url() -> str:
    """Get the URL for the Squid Proxy container."""
    return f"http://{_SQUID_PROXY_ALIAS}:{_SQUID_PROXY_PORT}"


def _ensure_squid_proxy_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_SQUID_PROXY_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_squid_proxy_image(specification, image_reference)
    return image_reference


def _create_squid_proxy_container_name(
    run_identifier: str,
) -> str:
    return f"squid-proxy-{run_identifier}"


def _create_squid_proxy_image(
    specification: MetisaSpecification,
    image_reference: str,
) -> None:
    dockerfile_location = _get_dockerfile_location()
    build_context_path = dockerfile_location.parent

    temporary_dir = tempfile.mkdtemp()
    metisa_conf_file = os.path.join(temporary_dir, "metisa-allow.conf")
    metisa_conf_contents = _create_metisa_allow_conf(specification)
    with open(metisa_conf_file, "w", encoding="utf-8") as file:
        file.write(metisa_conf_contents)

    if not Path(metisa_conf_file).exists():
        raise RuntimeError("Could not create metisa-allow.conf file for Squid Proxy.")

    try:
        build_docker_image(
            image_reference=image_reference,
            dockerfile_path=dockerfile_location,
            build_context_path=build_context_path,
            named_build_contexts={"temporary_dir": Path(temporary_dir)},
        )
    finally:
        shutil.rmtree(temporary_dir)


def _get_dockerfile_location() -> Path:
    dockerfile_location = Path(__file__).with_name("dockerfile")
    if not dockerfile_location.exists():
        raise RuntimeError("Dockerfile is not available.")
    return dockerfile_location


def _generate_image_tag(
    specification: MetisaSpecification,
) -> str:
    if specification.squid_proxy is None:
        raise RuntimeError("Specification did not contain a [squid_proxy] table.")
    collection: list[str] = list(specification.squid_proxy.allowed_domains)
    collection.extend(list(specification.squid_proxy.allowed_ip_addresses))
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"


# The following `metisa.toml` fragment:
#
#   [squid_proxy]
#   allowed_domains = [".example.com"]
#   allowed_ip_addresses = [
#       "93.184.216.34",
#       "2606:2800:220:1:248:1893:25c8:1946",
#   ]
#
# should produce the following `.conf` file:
#
#   acl metisa_allowed_domains dstdomain .example.com
#   acl metisa_allowed_ip_addresses dst 93.184.216.34 2606:2800:220:1:248:1893:25c8:1946
#
#   http_access allow metisa_allowed_domains
#   http_access allow metisa_allowed_ip_addresses


def _create_metisa_allow_conf(
    specification: MetisaSpecification,
) -> str:
    if not specification.squid_proxy:
        return ""

    acl_list: list[str] = []
    http_access_list: list[str] = []

    if specification.squid_proxy.allowed_domains:
        joined = " ".join(specification.squid_proxy.allowed_domains)
        list_name = "metisa_allowed_domains"
        acl_list.append(f"acl {list_name} dstdomain {joined}")
        http_access_list.append(f"http_access allow {list_name}")

    if specification.squid_proxy.allowed_ip_addresses:
        joined = " ".join(specification.squid_proxy.allowed_ip_addresses)
        list_name = "metisa_allowed_ip_addresses"
        acl_list.append(f"acl {list_name} dst {joined}")
        http_access_list.append(f"http_access allow {list_name}")

    if not acl_list and not http_access_list:
        return ""

    acl_lines = "\n".join(acl_list)
    http_access_lines = "\n".join(http_access_list)

    return f"{acl_lines}\n\n{http_access_lines}"
