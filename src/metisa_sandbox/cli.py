"""Command-line interface for the Metisa Sandbox."""

from __future__ import annotations

import sys

from .docker.docker_helper import (
    build_docker_image,
    docker_engine_started,
    docker_image_exists,
    run_workload_in_sandbox,
    start_docker_desktop,
)
from .specification.specification_helper import get_image_name, get_image_tag
from .terminal.terminal_helper import (
    get_first_argument,
    get_user_approval,
    print_error,
    print_info,
    print_warning,
)


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    workload_module = get_first_argument(argv)
    if not workload_module:
        example = "sample_agent"
        raise SystemExit(f"Usage: python -m metisa_sandbox {example}")

    image_name = get_image_name()
    image_tag = get_image_tag()

    try:
        docker_image_exitcode = _ensure_docker_image(image_name, image_tag)
        if docker_image_exitcode != 0:
            return docker_image_exitcode

        docker_workload_exitcode = _run_docker_workload(
            image_name, image_tag, workload_module
        )
        if docker_workload_exitcode != 0:
            return docker_workload_exitcode
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


def _ensure_docker_image(image_name: str, image_tag: str) -> int:
    if docker_engine_started():
        print_info("Docker Engine is reachable.")
    else:
        print_info("Docker Engine is not reachable.")
        if get_user_approval("Start Docker Desktop (Y/N)?"):
            print_info("Starting Docker Desktop...")
            start_docker_desktop()
            if docker_engine_started(timeout_seconds=128):
                print_info("Docker Engine started.")
            else:
                print_error("Docker Engine failed to start.")
                return 1
        else:
            print_warning("Docker Engine not started.")
            return 1

    if docker_image_exists(image_name, image_tag):
        print_info("Docker image already exists.")
        return 0

    print_info("Building Docker image...")
    image_built = build_docker_image(image_name, image_tag)

    if not image_built:
        print_error("Failed to build Docker image.")
        return 1

    print_info("Docker image built.")
    return 0


def _run_docker_workload(image_name: str, image_tag: str, workload_module: str) -> int:
    return_code = run_workload_in_sandbox(image_name, image_tag, workload_module)
    if return_code == 0:
        print_info("Docker workload completed.")
    else:
        print_error("Docker workload failed.")

    return return_code
