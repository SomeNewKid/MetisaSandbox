"""
Provides utility methods for working with Docker.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from metisa_common.models import Capability, MetisaSpecification
from metisa_common.specification_helper import (
    get_workload_specification_path,
    load_specification,
)

from .models import SandboxContext

_DOCKER_DESKTOP_EXE = (
    Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
    / "Docker"
    / "Docker"
    / "Docker Desktop.exe"
)


def docker_image_exists(image_name: str, image_tag: str) -> bool:
    docker_command_location = _get_docker_command_location()
    image_reference = create_image_reference(image_name, image_tag)
    result = subprocess.run(
        [docker_command_location, "image", "inspect", image_reference],
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0


def build_docker_image(image_name: str, image_tag: str) -> bool:
    """Ensure the image is available for the defined Dockerfile"""

    docker_command_location = _get_docker_command_location()

    image_reference = create_image_reference(image_name, image_tag)

    dockerfile_path = _get_dockerfile_location()
    build_context_path = dockerfile_path.parent

    result = subprocess.run(
        [
            docker_command_location,
            "build",
            "-t",
            image_reference,
            "-f",
            str(dockerfile_path),
            str(build_context_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Could not build Docker image.\n{output}")

    return True


def docker_engine_started(timeout_seconds: int = 0) -> bool:

    docker_command_location = _get_docker_command_location()

    if timeout_seconds < 1:
        return _docker_engine_available(docker_command_location)

    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if _docker_engine_available(docker_command_location):
            return True
        time.sleep(5)

    raise RuntimeError("Timed out waiting for Docker Engine to become available.")


def start_docker_desktop() -> None:
    if not _DOCKER_DESKTOP_EXE.exists():
        raise RuntimeError(
            f"Docker Desktop could not be found at {_DOCKER_DESKTOP_EXE}."
        )

    subprocess.Popen(
        [str(_DOCKER_DESKTOP_EXE)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_workload_in_sandbox(
    image_name: str, image_tag: str, workload_module: str
) -> int:
    specification = _load_workload_specification(workload_module)

    sandbox_context = _create_sandbox_context(image_name, image_tag)

    _create_docker_network(specification, sandbox_context)

    staged_source_path = _create_source_directory(sandbox_context, workload_module)

    arguments = _create_docker_run_arguments(
        specification,
        sandbox_context,
        staged_source_path,
        image_name,
        image_tag,
        workload_module,
    )

    log_file = _create_log_file(sandbox_context, arguments)

    return_code = _execute_sandbox_run(
        arguments, specification, sandbox_context, staged_source_path
    )

    _append_log_file(log_file, f"Return code: {return_code}")

    return return_code


def create_image_reference(image_name: str, image_tag: str) -> str:
    return f"{image_name}:{image_tag}"


def _load_workload_specification(workload_module: str):
    specification_path = get_workload_specification_path(workload_module)
    return load_specification(specification_path)


def _create_sandbox_context(image_name: str, image_tag: str) -> SandboxContext:
    run_identifier = _create_run_identifier()
    network_name = f"sandbox-{run_identifier}"
    host_source_path = Path.cwd() / "src"
    host_run_directory = _create_run_directory(run_identifier)
    output_dir_name = "output"
    host_output_path = _create_output_directory(host_run_directory, output_dir_name)

    return SandboxContext(
        image_name=image_name,
        image_tag=image_tag,
        identifier=run_identifier,
        network_name=network_name,
        host_run_path=host_run_directory,
        host_source_path=host_source_path,
        host_output_path=host_output_path,
    )


def _create_docker_run_arguments(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    staged_source_path: Path,
    image_name: str,
    image_tag: str,
    workload_module: str,
) -> list[str]:

    docker_command_location = _get_docker_command_location()

    image_reference = create_image_reference(image_name, image_tag)

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
    sandbox_context: SandboxContext,
    staged_source_path: Path,
) -> int:
    return_code = 999  # should be replaced when workload is run

    is_interactive = Capability.INTERACTIVE in specification.capabilities
    try:
        if is_interactive:
            process = subprocess.Popen(
                arguments,
                text=True,
            )

            return_code = process.wait()

        else:
            process = subprocess.Popen(
                arguments,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=0,
            )

            output_chunks = []

            if process.stdout is not None:
                while True:
                    chunk = process.stdout.read(1)
                    if chunk == "":
                        break

                    print(chunk, end="", flush=True)
                    output_chunks.append(chunk)

            return_code = process.wait()

    finally:
        _remove_docker_network(sandbox_context)

        _clean_up_run_directory(
            sandbox_context.host_run_path,
            staged_source_path,
            sandbox_context.host_output_path,
        )

    return return_code


def _create_docker_network(
    specification: MetisaSpecification, sandbox_context: SandboxContext
) -> None:
    docker_command_location = _get_docker_command_location()

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
    docker_command_location = _get_docker_command_location()

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


def _get_docker_command_location() -> str:
    docker_path = shutil.which("docker")
    if not docker_path:
        raise RuntimeError("Docker command is not available.")
    return docker_path


def _get_dockerfile_location() -> Path:
    dockerfile_location = Path(__file__).with_name("dockerfile")
    if not dockerfile_location.exists():
        raise RuntimeError("Dockerfile is not available.")
    return dockerfile_location


def _docker_engine_available(docker_command_location: str) -> bool:
    docker_command_location = _get_docker_command_location()

    result = subprocess.run(
        [docker_command_location, "info"],
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0


def _create_source_directory(
    sandbox_context: SandboxContext, workload_module: str
) -> Path:
    source_dir = sandbox_context.host_run_path / "source"
    source_dir.mkdir(parents=True, exist_ok=False)

    _copy_directories_into_staged(
        sandbox_context.host_source_path,
        source_dir,
        [
            sandbox_context.common_module_name,
            sandbox_context.runner_module_name,
            sandbox_context.probes_module_name,
            workload_module,
        ],
    )

    return source_dir


def _create_run_identifier() -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return f"run-{timestamp}"


def _create_run_directory(run_identifier: str) -> Path:
    run_directory = Path.cwd() / ".runs" / run_identifier
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_directory


def _create_output_directory(host_run_directory: Path, output_dir_name: str) -> Path:
    output_directory = host_run_directory / output_dir_name
    output_directory.mkdir(parents=True, exist_ok=False)
    return output_directory


def _create_log_file(sandbox_context: SandboxContext, arguments: list[str]) -> Path:
    logs_dir = sandbox_context.host_run_path / ".logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "docker.txt"

    with log_file.open("w", encoding="utf-8") as file:
        file.write("Running Docker container\n")
        file.write("Command: ")
        file.write(" ".join(arguments))
        file.write("\n")
        file.write("Image: ")
        file.write(sandbox_context.image_reference)
        file.write("\n")

    return log_file


def _append_log_file(log_file: Path, message: str) -> None:
    with log_file.open("a", encoding="utf-8") as file:
        file.write(message)
        file.write("\n")


def _copy_directories_into_staged(
    source_directory: Path, target_directory: Path, child_directories: list[str]
) -> None:
    for child_directory in child_directories:
        from_dir = source_directory / child_directory
        to_dir = target_directory / child_directory
        shutil.copytree(from_dir, to_dir)


def _clean_up_run_directory(
    host_run_directory: Path,
    staged_source_path: Path,
    output_directory: Path,
) -> None:
    output_logs_dir = output_directory / ".logs"
    if output_logs_dir.exists():
        run_logs_dir = host_run_directory / ".logs"
        run_logs_dir.mkdir(parents=True, exist_ok=True)
        for item in output_logs_dir.iterdir():
            shutil.move(item, run_logs_dir)
        output_logs_dir.rmdir()

    if staged_source_path.exists():
        shutil.rmtree(staged_source_path, ignore_errors=False)
