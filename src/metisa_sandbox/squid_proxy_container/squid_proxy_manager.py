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
    metisa_specification: MetisaSpecification,
    sandbox_context: SandboxContext,
) -> str:
    """Create the Squid Proxy container and connect it to the Docker networks."""
    image_name = ensure_squid_proxy_image_exists(metisa_specification)
    container_name = _create_squid_proxy_container_name(sandbox_context.run_identifier)

    arguments = [
        "--network",
        sandbox_context.egress_network_name,
        "--name",
        container_name,
        image_name,
    ]
    create_docker_container(arguments)
    connect_container_to_docker_network(
        container_name=container_name,
        network_name=sandbox_context.private_network_name,
        aliases=(_SQUID_PROXY_ALIAS,),
    )
    start_docker_container(container_name)
    started_successfully = inspect_docker_container(container_name)
    if not started_successfully:
        raise RuntimeError("Squid Proxy application failed to start.")

    return container_name


def ensure_squid_proxy_image_exists(
    specification: MetisaSpecification,
) -> str:
    """Ensure that the Squid Proxy Docker image exists."""
    image_tag = _generate_image_tag(specification)
    image_reference = f"{_SQUID_PROXY_IMAGE_NAME}:{image_tag}"
    if not docker_image_exists(image_reference):
        _create_squid_proxy_image(specification, image_reference)
    return image_reference


def get_squid_proxy_url() -> str:
    """Get the URL of the Squid Proxy."""
    return f"http://{_SQUID_PROXY_ALIAS}:{_SQUID_PROXY_PORT}"


def _create_squid_proxy_container_name(
    run_identifier: str,
) -> str:
    return f"squid-proxy-{run_identifier}"


def _create_squid_proxy_image(
    metisa_specification: MetisaSpecification,
    image_reference: str,
) -> None:
    dockerfile_location = _get_dockerfile_location()
    build_context_path = dockerfile_location.parent

    temporary_dir = tempfile.mkdtemp()
    metisa_conf_file = os.path.join(temporary_dir, "metisa-allow.conf")
    metisa_conf_contents = _create_metisa_allow_conf(metisa_specification)
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
        joined = " .".join(specification.squid_proxy.allowed_ip_addresses)
        list_name = "metisa_allowed_ip_addresses"
        acl_list.append(f"acl {list_name} dst {joined}")
        http_access_list.append(f"http_access allow {list_name}")

    if not acl_list and not http_access_list:
        return ""

    acl_lines = "\n".join(acl_list)
    http_access_lines = "\n".join(http_access_list)

    return f"{acl_lines}\n\n{http_access_lines}"
