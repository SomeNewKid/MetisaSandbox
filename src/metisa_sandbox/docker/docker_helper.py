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

from metisa_common.models import Capability
from metisa_common.specification_helper import load_specification

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
    image_name: str, 
    image_tag: str, 
    workload_module: str, 
    specification_path: Path
) -> int:
    if not specification_path.is_file():
        raise ValueError(f"Module '{workload_module}' does not contain metisa.toml.")
    specification = load_specification(specification_path)
    
    docker_command_location = _get_docker_command_location()
    image_reference = create_image_reference(image_name, image_tag)
    run_identifier = _create_run_identifier()
    network_name = f"sandbox-{run_identifier}"

    _create_docker_network(network_name, docker_command_location)

    common_module_name = "metisa_common"
    runner_module_name = "metisa_runner"
    probes_module_name = "metisa_probes"
    guest_source_dir = "/sandbox-source"
    guest_output_dir = "/sandbox-output"
    guest_work_dir = "/sandbox-work"
    host_source_path = Path.cwd() / "src"
    host_run_directory = _create_run_directory(run_identifier)
    output_dir_name = "output"
    host_output_path = _create_output_directory(host_run_directory, output_dir_name)

    is_interactive = Capability.INTERACTIVE in specification.capabilities

    arguments = [
        docker_command_location,
        "run",
        "--rm",  # remove after workload completes
        "--read-only",
    ]

    arguments.extend([
        "--network",
        network_name,
        "--network-alias",
        "metisa-workload",
    ])

    if is_interactive:
        arguments.extend([
            "--interactive", # keeps stdin open
            "--tty", # allocates a pseudo-terminal
        ])

    staged_source_path = _create_source_directory(host_run_directory)
    _copy_directories_into_staged(
        host_source_path,
        staged_source_path,
        [
            common_module_name,
            runner_module_name,
            probes_module_name,
            workload_module
        ]
    )

    arguments.extend([
        "--volume",
        f"{staged_source_path}:{guest_source_dir}:ro",
        "--volume",
        f"{host_output_path}:{guest_output_dir}:rw",
        "--tmpfs",
        guest_work_dir,
        "--env",
        f"SANDBOX_OUTPUT_DIR={guest_output_dir}",
        "--workdir",
        guest_source_dir,
        image_reference,
        "python",
        "-m",
        runner_module_name,
        workload_module,
    ])

    log_file = _get_log_file(host_run_directory)

    return_code = 999 # should be replaced when workload is run

    with log_file.open("w", encoding="utf-8") as file:
        file.write("Running Docker container\n")
        file.write("Command: ")
        file.write(" ".join(arguments))
        file.write("\n")
        file.write("Image: ")
        file.write(image_reference)
        file.write("\n")

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

        with log_file.open("a", encoding="utf-8") as file:
            file.write("Return code: ")
            file.write(str(return_code))
            file.write("\n")

        _remove_docker_network(network_name, docker_command_location)

        _clean_up_run_directory(
            host_run_directory, 
            staged_source_path, 
            output_dir_name
        )

    return return_code


def create_image_reference(image_name: str, image_tag: str) -> str:
    return f"{image_name}:{image_tag}"


def _create_docker_network(network_name: str, docker_command_location: str) -> None:
    result = subprocess.run(
        [
            docker_command_location,
            "network",
            "create",
            "--internal",
            network_name,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Could not create Docker network\n{output}")


def _remove_docker_network(network_name: str, docker_command_location: str) -> None:
    result = subprocess.run(
        [
            docker_command_location,
            "network",
            "rm",
            network_name,
        ],
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


def _create_source_directory(host_run_directory: Path) -> Path:
    source_dir = host_run_directory / "source"
    source_dir.mkdir(parents=True, exist_ok=False)

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


def _get_log_file(host_run_directory: Path) -> Path:
    logs_dir = host_run_directory / ".logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "docker.txt"

    return log_file


def _copy_directories_into_staged(
    source_directory: Path,
    target_directory: Path,
    child_directories: list[str]
) -> None:
    for child_directory in child_directories:
        from_dir = source_directory / child_directory
        to_dir = target_directory / child_directory
        shutil.copytree(from_dir, to_dir)


def _clean_up_run_directory(
    host_run_directory: Path, 
    staged_source_path: Path, 
    output_dir_name: str,
) -> None:
    output_logs_dir = host_run_directory / output_dir_name / ".logs"
    if output_logs_dir.exists():
        run_logs_dir = host_run_directory / ".logs"
        run_logs_dir.mkdir(parents=True, exist_ok=True)
        for item in output_logs_dir.iterdir():
            shutil.move(item, run_logs_dir)
        output_logs_dir.rmdir()

    if staged_source_path.exists():
        shutil.rmtree(staged_source_path, ignore_errors=False)