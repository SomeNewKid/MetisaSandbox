"""Provides utility methods for working with Docker."""

from __future__ import annotations

import subprocess
from pathlib import Path

from metisa_common.models import Capability, MetisaSpecification

from .docker_engine import get_docker_command_location
from .models import SandboxContext
from .run_workspace import (
    append_log_file,
    clean_up_run_directory,
    clean_up_staged_source,
    create_log_file,
    create_sandbox_context,
    create_staged_source_directory,
)


def run_workload_in_sandbox(
    specification: MetisaSpecification,
    image_reference: str,
    workload_module: str,
) -> int:
    """Run the specified workload in a Docker sandbox."""
    is_network_required = Capability.NETWORK in specification.capabilities

    sandbox_context: SandboxContext | None = None
    log_file: Path | None = None
    staged_source_path: Path | None = None
    network_created = False
    return_code: int | None = None

    try:
        sandbox_context = create_sandbox_context(image_reference)
        log_file = create_log_file(sandbox_context)

        staged_source_path = create_staged_source_directory(
            sandbox_context, workload_module
        )

        arguments = _create_docker_run_arguments(
            specification,
            sandbox_context,
            image_reference,
            staged_source_path,
            workload_module,
            is_network_required,
        )

        append_log_file(log_file, [f"Arguments: {' '.join(arguments)}"])

        if is_network_required:
            _create_docker_network(specification, sandbox_context)
            network_created = True

        return_code = _execute_sandbox_run(arguments, specification)

        return return_code

    except Exception as error:
        if log_file is not None:
            append_log_file(log_file, [f"Error: {error}"])
        raise

    finally:
        try:
            if network_created and sandbox_context is not None:
                _remove_docker_network(sandbox_context)

        finally:
            if sandbox_context is not None:
                clean_up_run_directory(
                    sandbox_context.host_run_path,
                    sandbox_context.host_output_path,
                )

            if staged_source_path is not None:
                clean_up_staged_source(staged_source_path)

            if log_file is not None and return_code is not None:
                append_log_file(log_file, [f"Return code: {return_code}"])


def _create_docker_run_arguments(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    image_reference: str,
    staged_source_path: Path,
    workload_module: str,
    is_network_required: bool,
) -> list[str]:

    docker_command_location = get_docker_command_location()

    is_interactive = Capability.INTERACTIVE in specification.capabilities
    arguments = [
        docker_command_location,
        "run",
    ]

    # Run as the sandbox user
    uid = 10001 # sandbox user
    gid = 10001 # sandbox group
    arguments.extend([
        "--user",
        f"{uid}:{gid}"
    ])

    # Remove the container after its workload completes
    arguments.extend(
        [
            "--rm",
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

    if is_network_required:
        arguments.extend(
            [
                "--network",
                sandbox_context.network_name,
                "--network-alias",
                "metisa-workload",
            ]
        )
    else:
        arguments.extend(
            [
                "--network",
                "none",
            ]
        )

    if is_interactive:
        arguments.extend(
            [
                "--interactive",  # keeps stdin open
                "--tty",  # allocates a pseudo-terminal
            ]
        )

    arguments.extend(
        [
            "--volume",
            f"{staged_source_path}:{sandbox_context.guest_source_dir}:ro",
            "--volume",
            f"{sandbox_context.host_output_path}:{sandbox_context.guest_output_dir}:rw",
            "--tmpfs",
            sandbox_context.guest_work_dir,
            "--env",
            f"SANDBOX_OUTPUT_DIR={sandbox_context.guest_output_dir}",
            "--workdir",
            sandbox_context.guest_source_dir,
            image_reference,
            f"{sandbox_context.guest_python_venv}/bin/python",
            "-m",
            sandbox_context.runner_module_name,
            workload_module,
        ]
    )

    return arguments


def _execute_sandbox_run(
    arguments: list[str],
    specification: MetisaSpecification,
) -> int:
    is_interactive = Capability.INTERACTIVE in specification.capabilities

    if is_interactive:
        process = subprocess.Popen(
            arguments,
            text=True,
        )

        return process.wait()

    process = subprocess.Popen(
        arguments,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=0,
    )

    if process.stdout is not None:
        while True:
            chunk = process.stdout.read(1)
            if chunk == "":
                break

            print(chunk, end="", flush=True)

    return process.wait()


def _create_docker_network(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
) -> None:
    docker_command_location = get_docker_command_location()

    # Make temporary use of specification argument
    is_networked = Capability.NETWORK in specification.capabilities
    print(f"[TEMP] is_networked: {is_networked}")

    arguments = [
        docker_command_location,
        "network",
        "create",
    ]

    arguments.extend(
        [
            "--internal",
        ]
    )

    arguments.extend(
        [
            sandbox_context.network_name,
        ]
    )

    result = subprocess.run(
        args=arguments,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Could not create Docker network\n{output}")


def _remove_docker_network(
    sandbox_context: SandboxContext,
) -> None:
    docker_command_location = get_docker_command_location()

    arguments = [
        docker_command_location,
        "network",
        "rm",
        sandbox_context.network_name,
    ]

    result = subprocess.run(
        args=arguments,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Could not remove Docker network\n{output}")
