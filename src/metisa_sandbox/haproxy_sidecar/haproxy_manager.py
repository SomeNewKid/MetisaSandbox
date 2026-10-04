"""Manage an HAProxy sidecar."""

from __future__ import annotations

import os
import shutil
import tempfile
import textwrap
from pathlib import Path

from metisa_common.specification_helper import generate_image_tag
from metisa_common.specification_models import MetisaSpecification

from ..docker.docker_container import (
    create_docker_container,
    execute_docker_command,
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
_HAPROXY_ALIAS = "metisa-haproxy"
_HAPROXY_PORT = 8404
_HAPROXY_IMAGE_NAME = "metisa-haproxy"


def create_haproxy_container(
    metisa_specification: MetisaSpecification,
    sandbox_context: SandboxContext,
) -> str:
    """Create the HAProxy container and connect it to the Docker networks."""
    image_name = _ensure_haproxy_image_exists(metisa_specification)
    container_name = _create_haproxy_container_name(sandbox_context.run_identifier)

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
            "nofile=512:512",
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
        aliases=(_HAPROXY_ALIAS,),
    )

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("HAProxy sidecar failed to start.")

    _verify_haproxy_configuration(container_name)

    return container_name


# Verify HAProxy configuration inside the container.
# This must be done after the container is attached to the network and started,
# because the configuration file may include an instruction like this:
#
#   frontend listener_3306
#       bind ipv4@metisa-haproxy:3306
#       mode tcp
#       default_backend destination_3306
#
# The metisa-haproxy host name must be resolved by the container's DNS,
# which is not available during image building or container creation.
def _verify_haproxy_configuration(
    container_name: str,
) -> None:
    """Verify the HAProxy configuration inside the container."""
    exitcode, message = execute_docker_command([
        container_name, 
        "haproxy", 
        "-c", 
        "-f", 
        "/etc/haproxy/haproxy.cfg"
    ])
    if exitcode != 0:
        raise RuntimeError(f"HAProxy configuration verification failed: {message}")


def _ensure_haproxy_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_HAPROXY_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_haproxy_image(specification, image_reference)
    return image_reference


def _create_haproxy_container_name(
    run_identifier: str,
) -> str:
    return f"metisa-haproxy-{run_identifier}"


def _create_haproxy_image(
    metisa_specification: MetisaSpecification,
    image_reference: str,
) -> None:
    dockerfile_location = _get_dockerfile_location()
    build_context_path = dockerfile_location.parent

    temporary_dir = tempfile.mkdtemp()
    haproxy_cfg_file = os.path.join(temporary_dir, "haproxy.cfg")
    haproxy_cfg_contents = _create_haproxy_cfg(metisa_specification)
    with open(haproxy_cfg_file, "w", encoding="utf-8") as file:
        file.write(haproxy_cfg_contents)

    if not Path(haproxy_cfg_file).exists():
        raise RuntimeError("Could not create haproxy.cfg file for HAProxy.")

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
    if specification.haproxy is None:
        raise RuntimeError("Specification did not contain an [haproxy] table.")
    collection: list[str] = []
    for backend in specification.haproxy.backends:
        collection.append(f"{backend.listen_port}|{backend.host}|{backend.port}")
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"


# The following `metisa.toml` fragment:
#
#     [haproxy]
#     backends = [
#        { listen_port = 3306, host = "host.docker.internal", port = 3306 },
#     ]
#
# should produce the following skeletal `haproxy.cfg` file:
#
#   frontend listener_3306
#       bind :3306
#       mode tcp
#       default_backend destination_3306
#
#   backend destination_3306
#       mode tcp
#       server database host.docker.internal:3306 check
#
def _create_haproxy_cfg(
    specification: MetisaSpecification,
) -> str:
    if not specification.haproxy:
        return ""

    backends = specification.haproxy.backends

    instructions: list[str] = []

    inactivity_timeout_seconds = 120
    finish_timeout_seconds = 60

    instructions.append(textwrap.dedent(
        """
        global
            # maximum number of concurrent connections
            maxconn 64
            log stdout format raw local0
        """
    ).strip())

    instructions.append(textwrap.dedent(
        f"""
        defaults
            retries 3
            # maximum time to wait for a successful TCP connection to backend server
            timeout connect 5s

             # maximum inactivity time on the client side
            timeout client {inactivity_timeout_seconds}s
            timeout client-fin {finish_timeout_seconds}s

            # maximum inactivity time on the backend server side
            timeout server {inactivity_timeout_seconds}s
            timeout server-fin {finish_timeout_seconds}s
        """
    ).strip())

    # Loopback-only HTTP monitoring frontend
    # used by HEALTHCHECK in dockerfile.
    instructions.append(textwrap.dedent(
        f"""
        frontend appliance_health
            bind 127.0.0.1:{_HAPROXY_PORT}
            mode http
            monitor-uri /health
        """
    ).strip())

    for backend in backends:
        instructions.append(textwrap.dedent(
            f"""
            frontend listener_{backend.listen_port}
                bind ipv4@metisa-haproxy:{backend.listen_port}
                mode tcp
                log global
                option tcplog             
                default_backend destination_{backend.listen_port}

            backend destination_{backend.listen_port}
                mode tcp
                server database {backend.host}:{backend.port} check
            """
        ).strip())

    final_linefeed_required_by_haproxy = "\n"
    contents = "\n\n".join(instructions) + final_linefeed_required_by_haproxy

    with open("c:\\temp\\haproxy.cfg", "w", encoding="utf-8") as file:
        file.write(contents)

    return contents
