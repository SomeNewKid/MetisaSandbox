"""Manage a LLM Server sidecar."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
)
from metisa_common.specification_models import LlmModel, MetisaSpecification

from ..docker.docker_container import (
    create_docker_container,
    inspect_docker_container,
    start_docker_container,
)
from ..docker.docker_image import (
    build_docker_image,
    docker_image_exists,
)
from ..sandbox_context import SandboxContext

LLM_CONTAINER_ALIAS_PREFIX = "metisa-llm-"
LLM_CONTAINER_NAME_PREFIX = "metisa-llm-server-"
_IMAGE_FORMAT_VERSION = 1
_LLM_SERVER_IMAGE_NAME = "metisa-llm-server"


def create_llm_server_containers(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
) -> list[str]:
    """Create and start LLM Server containers."""
    image_name = _ensure_llm_server_image_exists(specification)
    container_names: list[str] = []

    if not specification.llm_server:
        return container_names

    for llm_model in specification.llm_server.models:
        container_name = _create_llm_server_container(
            llm_model, sandbox_context, image_name
        )
        container_names.append(container_name)

    return container_names


def _create_llm_server_container(
    llm_model: LlmModel,
    sandbox_context: SandboxContext,
    image_name: str,
) -> str:
    container_name = _create_llm_server_container_name(
        llm_model, sandbox_context.run_identifier
    )
    container_alias = _create_llm_server_container_alias(
        llm_model,
    )

    arguments = [
        "--name",
        container_name,
        "--network",
        sandbox_context.workload_network_name,
        "--network-alias",
        container_alias,
    ]

    # Mount the model file into the container.
    local_relative = llm_model.repo.replace("/", "\\")
    local_model_path = (
        Path(r"C:\Git\__Models")
        / local_relative
        / llm_model.revision
        / llm_model.filename
    )
    if not local_model_path.is_file():
        raise FileNotFoundError(f"Model file not found at {local_model_path}")
    local_model_location = str(local_model_path)
    container_model_location = f"/models/{llm_model.filename}"
    arguments.extend(
        [
            "--mount",
            f"type=bind,source={local_model_location},target={container_model_location},readonly",
        ]
    )

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

    # Allow the container more time to start.
    # Logs show can take nearly five minutes.
    arguments.extend(
        [
            "--health-start-period",
            "360s",
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
    # Disabled because LLM inference is already slow enough.
    # arguments.extend(
    #     [
    #         "--cpus",
    #         "4",
    #     ]
    # )

    # Set memory limits for the container.
    arguments.extend(
        [
            "--memory",
            "3g",
            "--memory-swap",  # no additional swap beyond the memory limit
            "3g",
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
            "--model",
            container_model_location,
            "--alias",
            llm_model.alias,
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
            "--ctx-size",
            "2048",
            "--parallel",
            "1",
            "--threads",
            "4",
            "--threads-batch",
            "4",
            # "--log-verbosity",
            # "5",
        ]
    )

    print(f"Creating {container_alias}")
    create_docker_container(arguments)

    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError(f"LLM server '{container_alias}' failed to start.")
    print(f"Created {container_alias}")

    return container_name


def _ensure_llm_server_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_LLM_SERVER_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_llm_server_image(specification, image_reference)
    return image_reference


def _create_llm_server_container_name(
    llm_model: LlmModel,
    run_identifier: str,
) -> str:
    return f"{LLM_CONTAINER_NAME_PREFIX}{run_identifier}-{llm_model.alias}"


def _create_llm_server_container_alias(
    llm_model: LlmModel,
) -> str:
    return f"{LLM_CONTAINER_ALIAS_PREFIX}{llm_model.alias}"


def _create_llm_server_image(
    specification: MetisaSpecification,
    image_reference: str,
) -> None:
    dockerfile_location = _get_dockerfile_location()
    build_context_path = dockerfile_location.parent

    build_docker_image(
        image_reference=image_reference,
        dockerfile_path=dockerfile_location,
        build_context_path=build_context_path,
    )


def _get_dockerfile_location() -> Path:
    dockerfile_location = Path(__file__).with_name("dockerfile")
    if not dockerfile_location.exists():
        raise RuntimeError("Dockerfile is not available.")
    return dockerfile_location


def _generate_image_tag(
    specification: MetisaSpecification,
) -> str:
    collection: list[str] = []
    hash = generate_image_tag(collection)
    return f"{_IMAGE_FORMAT_VERSION}-{hash}"
