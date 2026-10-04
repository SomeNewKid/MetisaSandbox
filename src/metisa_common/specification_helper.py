"""Provides utility methods for working with specifications."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from importlib.util import find_spec
from pathlib import Path

from .specification_models import (
    Capability,
    HaproxyBackend,
    HaproxySpecification,
    McpSidecarSpecification,
    MetisaSpecification,
    OllamaSidecarSpecification,
    SpecificationValidationError,
    SquidProxySpecification,
)
from .specification_validator import (
    validate_specification,
)

_IMAGE_FORMAT_VERSION = 1
_VALID_RESOLVERS = ("host",)


def get_workload_image_name() -> str:
    """Get the name of the Docker image for the Metisa workload container."""
    return "metisa-workload"


def get_image_tag(
    specification: MetisaSpecification,
) -> str:
    """Get a deterministic Docker image tag for the required capabilities."""
    ordered_capabilities = sorted(
        capability.value for capability in specification.capabilities
    )

    ordered_dependencies = sorted(
        dependency for dependency in specification.dependencies
    )

    ordered_collections: list[str] = list(value for value in ordered_capabilities)
    for value in ordered_dependencies:
        ordered_collections.append(value)

    return generate_image_tag(ordered_collections)


def generate_image_tag(collection: list[str]) -> str:
    """Generate a deterministic Docker image tag for the given collection of strings."""
    ordered_collections = sorted(collection)
    serialized_collections = json.dumps(
        ordered_collections, ensure_ascii=True, separators=(",", ":")
    )
    collections_hash = hashlib.sha256(
        serialized_collections.encode("utf-8")
    ).hexdigest()
    return f"{_IMAGE_FORMAT_VERSION}-{collections_hash}"


def get_workload_specification_path(
    workload_module: str,
) -> Path:
    """Get the path to the metisa.toml file in the specified workload_module."""
    module_spec = find_spec(workload_module)
    if module_spec is None:
        raise ValueError(f"Workload module '{workload_module}' was not found.")

    package_locations = module_spec.submodule_search_locations
    if package_locations is None:
        raise ValueError(f"Workload module '{workload_module}' must be a package.")

    package_location = next(iter(package_locations), None)
    if package_location is None:
        raise ValueError(f"Could not determine location of '{workload_module}'.")

    specification_path = Path(package_location) / "metisa.toml"
    if not specification_path.is_file():
        raise ValueError(f"Module '{workload_module}' does not contain metisa.toml.")

    return specification_path


def load_specification(
    file_path: Path,
) -> MetisaSpecification:
    """Load and validate the TOML specification file."""
    if not file_path.exists():
        raise ValueError("TOML specification file does not exist.")
    toml_content = file_path.read_text(encoding="utf-8")
    return parse_specification(toml_content)


def parse_specification(
    toml_content: str,
) -> MetisaSpecification:
    """Parse and validate the TOML specification file."""
    if not toml_content:
        raise ValueError("TOML specification file was empty")
    toml = tomllib.loads(toml_content)
    return _create_metisa_specification(toml)


def dependency_is_valid(
    dependency: str,
) -> bool:
    """Validate the TOML dependency value."""
    if not dependency.strip():
        print(f"Dependency '{dependency}' is empty or whitespace.")
        return False
    match = re.fullmatch(r"([a-zA-Z0-9_-]+)(==|>=|~=)([0-9]+(?:\.[0-9]+)*)", dependency)
    return match is not None


# Example in a `metisa.toml` file:
#   environs = [
#     "METISA_PROBE_1=hard-coded value",
#     "METISA_PROBE_2=${host:METISA_PROBE_2}",
#   ]
# The latter uses a simple version of the named-resolver pattern
# https://omegaconf.readthedocs.io/en/latest/custom_resolvers.html
def environ_is_valid(
    environ: str,
) -> bool:
    """Validate the TOML environ value."""
    try:
        _, value = _get_environ_name_value(environ)
    except ValueError:
        return False

    if not value.startswith("${"):
        return True  # hard-coded value

    if not value.endswith("}"):
        return False  # invalid name-resolver pattern

    resolver_pattern = value[2:-1]

    try:
        _, resolver_value = _get_environ_resolver_name_value(resolver_pattern)
    except ValueError:
        return False

    return resolver_value is not None


def get_resolved_environs(
    specification: MetisaSpecification,
) -> list[str]:
    """Resolve all environment variables specified in the Metisa specification."""
    resolved_list: list[str] = []

    for environ in specification.environs:
        if not environ_is_valid(environ):
            raise ValueError(f"Environ is not valid: {environ}")
        resolved_env = _resolve_environ(environ)
        resolved_list.append(resolved_env)

    return resolved_list


def _resolve_environ(
    environ: str,
) -> str:
    name, value = _get_environ_name_value(environ)
    if value.startswith("${") and value.endswith("}"):
        resolver_pattern = value[2:-1]
        value = _resolve_environ_value(resolver_pattern)
    return f"{name}={value}"


def _get_environ_name_value(
    environ: str,
) -> tuple[str, str]:
    if not environ:
        raise ValueError("Environ is not valid.")
    error_message = f"Environ is not valid: '{environ}'"

    name_value = environ.split("=", 1)
    if len(name_value) != 2:
        raise ValueError(error_message)

    name = name_value[0]
    if not name:
        raise ValueError(error_message)

    value = name_value[1]

    return name, value


# Example in a `metisa.toml` file:
#   environs = [
#     "METISA_PROBE_2=${host:METISA_PROBE_2}",
#   ]
# This uses a simple version of the named-resolver pattern
# https://omegaconf.readthedocs.io/en/latest/custom_resolvers.html
def _get_environ_resolver_name_value(
    resolver_pattern: str,
) -> tuple[str, str]:
    if not resolver_pattern:
        raise ValueError("Environ resolver pattern not valid.")
    error_message = f"Environ resolver pattern not valid: {resolver_pattern}"

    name_value = resolver_pattern.split(":")
    if len(name_value) != 2:
        raise ValueError(error_message)

    name = name_value[0]
    if name not in _VALID_RESOLVERS:
        raise ValueError(f"Environ resolver type not supported: {name}")

    value = name_value[1]
    if not value:
        raise ValueError(error_message)

    return name, value


def _resolve_environ_value(
    resolver_pattern: str,
) -> str:
    name, value = _get_environ_resolver_name_value(resolver_pattern)
    if name not in _VALID_RESOLVERS:
        raise ValueError(f"Environ resolver not supported: {name}")
    if name == "host":
        return _resolve_environ_host_value(value)
    raise ValueError(f"Environ resolver not supported: {name}")


def _resolve_environ_host_value(
    name: str,
) -> str:
    return os.environ.get(name, "")


def _create_metisa_specification(
    toml: dict[str, object],
) -> MetisaSpecification:
    VALID_KEYS = frozenset(
        {
            "agent_name",
            "capabilities",
            "dependencies",
            "environs",
        }
    )

    VALID_TABLES = frozenset(
        {
            "squid_proxy",
            "haproxy",
            "ollama_sidecar",
            "mcp_sidecar",
        }
    )

    _validate_known_keys(toml, "TOML specification", VALID_KEYS | VALID_TABLES)
    _validate_known_tables(toml, "TOML specification", VALID_TABLES)

    agent_name = _get_agent_name(toml)
    capabilities = _get_capabilities(toml)
    dependencies = _get_dependencies(toml)
    environs = _get_environs(toml)
    haproxy = _get_haproxy_specfication(toml)
    squid_proxy = _get_squid_proxy_specification(toml)
    ollama_sidecar = _get_ollama_sidecar_specification(toml)
    mcp_sidecar = _get_mcp_sidecar_specification(toml)
    specification = MetisaSpecification(
        agent_name=agent_name,
        capabilities=capabilities,
        dependencies=dependencies,
        environs=environs,
        haproxy=haproxy,
        squid_proxy=squid_proxy,
        ollama_sidecar=ollama_sidecar,
        mcp_sidecar=mcp_sidecar,
    )

    validate_specification(specification)
    return specification


def _get_agent_name(
    toml: dict[str, object],
) -> str:
    agent_name = toml.get("agent_name")

    if agent_name is None:
        error = "TOML specification requires a agent_name string."
        raise SpecificationValidationError(error)

    if not isinstance(agent_name, str):
        error = "TOML specification agent_name must be a string."
        raise SpecificationValidationError(error)

    agent_name = agent_name.strip()
    if len(agent_name) == 0:
        error = "TOML specification agent_name must be a non-empty string."
        raise SpecificationValidationError(error)

    return agent_name


def _get_capabilities(
    toml: dict[str, object],
) -> frozenset[Capability]:
    raw_capabilites = _get_str_tuple(
        toml.get("capabilities"), "TOML specification capabilities"
    )

    capabilities: set[Capability] = set()

    for raw_capability in raw_capabilites:
        try:
            capability = Capability(raw_capability)
        except ValueError as error:
            raise SpecificationValidationError(
                f"TOML specification capability '{raw_capability}' is not supported."
            ) from error

        capabilities.add(capability)

    return frozenset(capabilities)


def _get_dependencies(
    toml: dict[str, object],
) -> frozenset[str]:
    raw_dependencies = _get_str_tuple(
        toml.get("dependencies"), "TOML specificiation dependencies"
    )

    dependencies: set[str] = set()

    for raw_dependency in raw_dependencies:
        if not isinstance(raw_dependency, str):
            raise SpecificationValidationError(
                f"TOML specification dependency '{raw_dependency}' is not supported."
            )
        if not dependency_is_valid(raw_dependency):
            raise SpecificationValidationError(
                f"TOML specification dependency '{raw_dependency}' "
                "is not pinned or not valid."
            )
        dependencies.add(raw_dependency)

    return frozenset(dependencies)


def _get_environs(
    toml: dict[str, object],
) -> frozenset[str]:
    raw_environs = _get_str_tuple(toml.get("environs"), "TOML specification environs")

    environs: set[str] = set()

    for raw_environ in raw_environs:
        if not isinstance(raw_environ, str):
            raise SpecificationValidationError(
                f"TOML specification environ '{raw_environ}' is not supported."
            )
        if not environ_is_valid(raw_environ):
            raise SpecificationValidationError(
                f"TOML specification environ '{raw_environ}' is not valid."
            )
        environs.add(raw_environ)

    return frozenset(environs)


def _get_haproxy_specfication(
    toml: dict[str, object],
) -> HaproxySpecification | None:
    haproxy = toml.get("haproxy")
    if not haproxy:
        return None

    if not isinstance(haproxy, dict):
        raise SpecificationValidationError(
            "TOML specification haproxy must be a table."
        )

    HAPROXY_KEYS = frozenset(
        {
            "backends",
        }
    )

    _validate_known_keys(haproxy, "haproxy", HAPROXY_KEYS)

    backends: list[HaproxyBackend] = []

    raw_backends = haproxy.get("backends", [])
    if raw_backends is not None:
        if isinstance(raw_backends, str):
            raise SpecificationValidationError("HAProxy backends must be an array.")
        if not isinstance(raw_backends, list):
            raise SpecificationValidationError("HAProxy backends must be an array.")

        for raw_backend in raw_backends:
            if not isinstance(raw_backend, dict):
                error = "HAProxy backends must be an array of ojects"
                raise SpecificationValidationError(error)

            backend = _get_haproxy_backend(raw_backend)
            if backend in backends:
                error = (
                    "Duplicate HAProxy backend: "
                    f"listen_port={backend.listen_port}, "
                    f"host={backend.host}, "
                    f"port={backend.port}."
                )
                raise SpecificationValidationError(error)

            backends.append(backend)

    return HaproxySpecification(backends=tuple(backends))


def _get_haproxy_backend(
    definition: dict[str, object],
) -> HaproxyBackend:
    listen_port = definition.get("listen_port")
    if not listen_port:
        error = "HAProxy backend must specify a listen_port."
        raise SpecificationValidationError(error)
    if not isinstance(listen_port, int):
        error = "HAProxy backend must specify an integer listen_port."
        raise SpecificationValidationError(error)
    if listen_port < 1:
        error = "HAProxy backend must specify a positive integer listen_port."
        raise SpecificationValidationError(error)

    host = definition.get("host")
    if not host:
        error = "HAProxy backend must specify a host"
        raise SpecificationValidationError(error)
    if not isinstance(host, str):
        error = "HAProxy backend must specify a string host."
        raise SpecificationValidationError(error)
    if not host:
        error = "HAProxy backend must specify a valid host."
        raise SpecificationValidationError(error)

    port = definition.get("port")
    if not port:
        error = "HAProxy backend must specify a port."
        raise SpecificationValidationError(error)
    if not isinstance(port, int):
        error = "HAProxy backend must specify an integer port."
        raise SpecificationValidationError(error)
    if port < 1:
        error = "HAProxy backend must specify a positive integer port."
        raise SpecificationValidationError(error)

    return HaproxyBackend(listen_port=listen_port, host=host, port=port)


def _get_squid_proxy_specification(
    toml: dict[str, object],
) -> SquidProxySpecification | None:
    squid_proxy = toml.get("squid_proxy")
    if not squid_proxy:
        return None

    if not isinstance(squid_proxy, dict):
        raise SpecificationValidationError(
            "TOML specification squid_proxy must be a table."
        )

    SQUID_PROXY_KEYS = frozenset(
        {
            "allowed_domains",
            "allowed_ip_addresses",
        }
    )

    _validate_known_keys(squid_proxy, "squid_proxy", SQUID_PROXY_KEYS)

    allowed_domains = _get_str_tuple(
        squid_proxy.get("allowed_domains"), "Squid Proxy allowed domains"
    )

    allowed_ip_addresses = _get_str_tuple(
        squid_proxy.get("allowed_ip_addresses"), "Squid Proxy allowed IP addresses"
    )

    return SquidProxySpecification(
        allowed_domains=allowed_domains, allowed_ip_addresses=allowed_ip_addresses
    )


def _get_ollama_sidecar_specification(
    toml: dict[str, object],
) -> OllamaSidecarSpecification | None:

    ollama_sidecar = toml.get("ollama_sidecar")
    if not ollama_sidecar:
        return None

    if not isinstance(ollama_sidecar, dict):
        raise SpecificationValidationError(
            "TOML specification ollama_sidecar must be a table."
        )

    OLLAMA_KEYS = frozenset(
        {
            "models",
        }
    )

    _validate_known_keys(ollama_sidecar, "ollama_sidecar", OLLAMA_KEYS)

    models = _get_str_tuple(ollama_sidecar["models"], "Ollama models")

    return OllamaSidecarSpecification(models=models)


def _get_mcp_sidecar_specification(
    toml: dict[str, object],
) -> McpSidecarSpecification | None:
    mcp_sidecar = toml.get("mcp_sidecar")
    if not mcp_sidecar:
        return None

    if not isinstance(mcp_sidecar, dict):
        raise SpecificationValidationError(
            "TOML specification mcp_sidecar must be a table."
        )

    MCP_SIDECAR_KEYS = frozenset(
        {
            "tools",
            "resources",
        }
    )

    _validate_known_keys(mcp_sidecar, "mcp_sidecar", MCP_SIDECAR_KEYS)

    tools = _get_str_tuple(mcp_sidecar.get("tools"), "MCP Sidecar allowed domains")

    resources = _get_str_tuple(
        mcp_sidecar.get("resources"), "MCP Sidecar allowed IP addresses"
    )

    return McpSidecarSpecification(tools=tools, resources=resources)


def _validate_known_keys(
    table: dict[str, object],
    table_name: str,
    known_keys: frozenset[str],
) -> None:
    unknown_keys = set(table) - known_keys
    if not unknown_keys:
        return

    formatted_keys = ", ".join(sorted(unknown_keys))
    raise SpecificationValidationError(
        f"TOML specification {table_name} contains unknown keys: {formatted_keys}."
    )


def _validate_known_tables(
    toml: dict[str, object],
    table_name: str,
    known_keys: frozenset[str],
) -> None:
    for table_name in known_keys:
        if table_name not in toml:
            continue

        if not isinstance(toml[table_name], dict):
            raise SpecificationValidationError(
                f"TOML specification {table_name} must be a table."
            )


def _get_str_tuple(
    collection: object | None,
    section_name: str,
) -> tuple[str]:
    if collection is None:
        return tuple([])

    if isinstance(collection, str):
        error = f"{section_name} must be an array."
        raise SpecificationValidationError(error)

    if not isinstance(collection, list):
        error = f"{section_name} must be iterable."
        raise SpecificationValidationError(error)

    trimmed_values = []

    for item in iter(collection):
        if not isinstance(item, str):
            error = f"{section_name} must be strings."
            raise SpecificationValidationError(error)
        if not item:
            error = f"{section_name} must use non-empty strings."
            raise SpecificationValidationError(error)
        trimmed_value = item.strip()
        if len(trimmed_value) == 0:
            error = f"{section_name} must use non-whitespace strings."
            raise SpecificationValidationError(error)
        trimmed_values.append(item)

    return tuple(trimmed_values)


def _get_int_tuple(
    collection: object | None,
    section_name: str,
) -> tuple[int]:
    if not collection:
        return tuple([])

    if not isinstance(collection, list):
        error = f"{section_name} must be iterable."
        raise SpecificationValidationError(error)

    for item in iter(collection):
        if not isinstance(item, int):
            error = f"{section_name} must be integers."
            raise SpecificationValidationError(error)

    return tuple(collection)
