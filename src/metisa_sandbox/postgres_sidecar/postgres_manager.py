"""Manage a Postgres sidecar."""

from __future__ import annotations

from pathlib import Path

from metisa_common.specification_helper import (
    generate_image_tag,
    resolve_environs,
)
from metisa_common.specification_models import MetisaSpecification

from .._docker._docker_container import (
    create_docker_container,
    execute_docker_command,
)
from .._docker._docker_hardening import (
    harden_docker_container,
)
from .._docker._docker_image import (
    build_docker_image,
    docker_image_exists,
)
from .._sandbox_models import (
    ContainerCreationContext,
    ContainerCreationResult,
    SandboxContainer,
    SandboxContext,
)

_IMAGE_FORMAT_VERSION = 1
_POSTGRESQL_ALIAS = "metisa-postgres"
_POSTGRESQL_IMAGE_NAME = "metisa-postgres"
_POSTGRES_CONTAINER_NAME = "metisa-postgres-agent-memory"
_GUEST_STORAGE_DIRECTORY = "/var/lib/postgresql"
_GUEST_SCHEMA_FILE = "/etc/metisa/schema.sql"


def create_postgres_definition() -> SandboxContainer:
    """Return the definition of the Postgres container."""
    return SandboxContainer(
        "Postgres",
        "postgres",
        log_folder="postgres",
        log_files=[],
    )


def create_postgres_container(
    specification: MetisaSpecification,
    sandbox_context: SandboxContext,
    container_creation_context: ContainerCreationContext,
) -> ContainerCreationResult:
    """Create and start a Postgres sidecar container."""
    if not specification.postgres:
        raise RuntimeError("Metisa specification did not include a document section.")
    image_name = _ensure_postgres_image_exists(specification)

    # We're using a fixed container name to prevent
    # concurrent agents from starting separate database
    # servers against the same storage directory.
    container_name = _POSTGRES_CONTAINER_NAME
    # container_name = _create_postgres_container_name(sandbox_context.run_identifier)

    if not container_creation_context.network_names:
        raise RuntimeError("No network specified for the Postgres container.")
    network_name = container_creation_context.network_names[0]

    schema_file = Path(__file__).with_name("schema.sql").resolve()

    environs: list[str] = []

    arguments = [
        "--name",
        container_name,
        "--network",
        network_name,
        "--network-alias",
        _POSTGRESQL_ALIAS,
    ]

    # Mount temporary (in memory) filesystems.
    arguments.extend(
        [
            "--tmpfs",
            "/tmp:rw,size=64m,nosuid,nodev,noexec",
            "--tmpfs",
            "/var/run/postgresql:rw,size=1m,nosuid,nodev,noexec,uid=10012,gid=10012,mode=3775",
        ]
    )

    # Mount the database.
    arguments.extend(
        [
            "--mount",
            ("type=volume,source=metisa-agent-memory,target=/var/lib/postgresql"),
            "--mount",
            (f"type=bind,source={schema_file},target={_GUEST_SCHEMA_FILE},readonly"),
        ]
    )

    # Get environment variables
    resolved_environs = resolve_environs(specification.postgres.environs)
    environs.extend(resolved_environs)

    # Harden the container
    harden_docker_container(
        arguments=arguments,
        environs=environs,
        username="elephant",
        file_size_limit=None,
        memory="512m",
    )

    # The image name must be specified last in the arguments list.
    arguments.extend(
        [
            image_name,
        ]
    )

    create_docker_container(arguments)

    return ContainerCreationResult(container_name)


def initialize_postgres_schema(
    container_name: str,
) -> None:
    """Create missing memory tables in the running PostgreSQL database."""
    arguments = [
        container_name,
        "/bin/sh",
        "-c",
        (
            "exec psql "
            "--host=/var/run/postgresql "
            '--username="$POSTGRES_USER" '
            '--dbname="$POSTGRES_DB" '
            "--no-psqlrc "
            "--no-password "
            "--set=ON_ERROR_STOP=1 "
            "--single-transaction "
            f"--file={_GUEST_SCHEMA_FILE}"
        ),
    ]

    return_code, output = execute_docker_command(arguments)

    if return_code != 0:
        raise RuntimeError(f"Could not initialize PostgreSQL schema:\n{output}")


def _ensure_postgres_image_exists(
    specification: MetisaSpecification,
) -> str:
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_POSTGRESQL_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_postgres_image(specification, image_reference)
    return image_reference


def _create_postgres_container_name(
    run_identifier: str,
) -> str:
    return f"postgres-{run_identifier}"


def _create_postgres_image(
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
