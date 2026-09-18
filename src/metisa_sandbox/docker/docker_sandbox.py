"""
Provides utility methods for working with Docker.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from metisa_common.models import Capability, MetisaSpecification
from metisa_common.specification_helper import (
    get_workload_specification_path,
    load_specification,
)

from .docker_engine import get_docker_command_location
from .docker_image import create_image_reference
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
    image_name: str, image_tag: str, workload_module: str
) -> int:
    specification = _load_workload_specification(workload_module)

    sandbox_context: SandboxContext | None = None
    log_file: Path | None = None
    staged_source_path: Path | None = None
    network_created = False
    return_code: int | None = None

    try:
        sandbox_context = create_sandbox_context(image_name, image_tag)
        log_file = create_log_file(sandbox_context)

        staged_source_path = create_staged_source_directory(
            sandbox_context, workload_module
        )

        arguments = _create_docker_run_arguments(
            specification,
            sandbox_context,
            staged_source_path,
            workload_module,
        )

        append_log_file(log_file, [f"Arguments: {' '.join(arguments)}"])

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



def _create_image_reference(sandbox_context: SandboxContext) -> str:
    return create_image_reference(sandbox_context.image_name, sandbox_context.image_tag)


def _load_workload_specification(workload_module: str):
    specification_path = get_workload_specification_path(workload_module)
    return load_specification(specification_path)


def _create_docker_run_arguments(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    staged_source_path: Path,
    workload_module: str,
) -> list[str]:

    docker_command_location = get_docker_command_location()
    image_reference = _create_image_reference(sandbox_context)

    is_interactive = Capability.INTERACTIVE in specification.capabilities
    arguments = [
        docker_command_location,
        "run",
        "--rm",  # remove after workload completes
        "--read-only",
    ]

    arguments.extend(
        [
            "--network",
            sandbox_context.network_name,
            "--network-alias",
            "metisa-workload",
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
            "python",
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
    specification: MetisaSpecification, sandbox_context: SandboxContext
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


def _remove_docker_network(sandbox_context: SandboxContext) -> None:
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
