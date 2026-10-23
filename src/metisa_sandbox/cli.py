"""Command-line interface for the Metisa Sandbox."""

from __future__ import annotations

import sys

from metisa_common.specification_helper import (
    get_image_tag,
    get_workload_image_name,
    get_workload_specification_path,
    load_specification,
)
from metisa_common.specification_models import (
    MetisaSpecification,
)
from metisa_common.terminal_helper import (
    FAILURE_INDICATOR,
    SUCCESS_INDICATOR,
    terminal_status,
)

from ._docker._docker_engine import (
    docker_engine_started,
    start_docker_desktop,
)
from ._docker._docker_image import (
    create_image_reference,
    docker_image_exists,
)
from ._sandbox_manager import (
    run_metisa_container_workload_in_sandbox,
)
from ._utilities._terminal_helper import (
    get_first_argument,
    get_user_approval,
    print_error,
    print_info,
    print_warning,
)
from .metisa_container._metisa_container_image import (
    build_metisa_container_image,
)


def main(
    argv: list[str] | None = None,
) -> int:
    """Run the command-line interface."""
    workload_module = get_first_argument(argv)
    if not workload_module:
        example = "sample_agent"
        raise SystemExit(f"Usage: python -m metisa_sandbox {example}")

    specification_path = get_workload_specification_path(workload_module)
    try:
        specification = load_specification(specification_path)
    except Exception as error:
        print_error(f"Failed to load specification: {error}")
        return 1

    image_name = get_workload_image_name()
    image_tag = get_image_tag(specification)
    image_reference = create_image_reference(image_name, image_tag)

    try:
        docker_image_exitcode = _ensure_metisa_container_image(
            specification, image_reference
        )
        if docker_image_exitcode != 0:
            return docker_image_exitcode

        docker_workload_exitcode = _run_metisa_container_workload(
            specification, image_reference, workload_module
        )
        if docker_workload_exitcode != 0:
            return docker_workload_exitcode
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


def _ensure_metisa_container_image(
    specification: MetisaSpecification,
    image_reference: str,
) -> int:
    if docker_engine_started():
        print_info(SUCCESS_INDICATOR + " Docker Engine is reachable.")
    else:
        print_info("Docker Engine is not reachable.")
        if get_user_approval("Start Docker Desktop (Y/N)?"):
            print_info("Starting Docker Desktop...")
            start_docker_desktop()
            if docker_engine_started(timeout_seconds=128):
                print_info(f"{SUCCESS_INDICATOR} Docker Engine started.")
            else:
                print_error(f"{FAILURE_INDICATOR} Docker Engine failed to start.")
                return 1
        else:
            print_warning(f"{FAILURE_INDICATOR} Docker Engine not started.")
            return 1

    image_alias = "Docker Metisa workload image"
    if docker_image_exists(image_reference):
        print_info(f"{SUCCESS_INDICATOR} {image_alias} already exists.")
        return 0

    with terminal_status(
        running=f"Building {image_alias}...",
        success=f"Built {image_alias}.",
        failure=f"Failed to build {image_alias}. Workload will not be run.",
    ):
        build_metisa_container_image(specification, image_reference)
        return 0


def _run_metisa_container_workload(
    specification: MetisaSpecification,
    image_reference: str,
    workload_module: str,
) -> int:
    return_code = run_metisa_container_workload_in_sandbox(
        specification, image_reference, workload_module
    )
    if return_code == 0:
        print_info(SUCCESS_INDICATOR + " Completed agent workload.")
    else:
        print_error(FAILURE_INDICATOR + " Could not complete agent workload.")

    return return_code
