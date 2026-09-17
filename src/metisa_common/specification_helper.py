"""
Provides utility methods for working with specifications.
"""

from __future__ import annotations

import tomllib
from importlib.util import find_spec
from pathlib import Path

from .models import (
    Capability,
    HaproxySpecification,
    McpSidecarSpecification,
    MetisaSpecification,
    OllamaSidecarSpecification,
    SpecificationValidationError,
    SquidProxySpecification,
)


def get_image_name() -> str:
    return "metisa-sandbox"


def get_image_tag() -> str:
    return "phase-2"


def get_workload_specification_path(workload_module: str) -> Path:
    """Gets the path to the metisa.toml file in the specified workload_module."""
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


def load_specification(file_path: Path) -> MetisaSpecification:
    """Load and validate the TOML specification file."""
    if not file_path.exists():
        raise ValueError("TOML specification file does not exist.")
    toml_content = file_path.read_text(encoding="utf-8")
    return parse_specification(toml_content)


def parse_specification(toml_content: str) -> MetisaSpecification:
    """Parse and validate the TOML specification file."""
    if not toml_content:
        raise ValueError("TOML specification file was empty")
    toml = tomllib.loads(toml_content)
    return _create_metisa_specification(toml)


def _create_metisa_specification(toml: dict[str, object]) -> MetisaSpecification:
    VALID_KEYS = frozenset({
        "schema_version",
        "workload_name",
        "capabilities",
    })

    VALID_TABLES = frozenset({
        "squid_proxy",
        "haproxy",
        "ollama_sidecar",
        "mcp_sidecar",
    })

    _validate_known_keys(toml, "TOML specification", VALID_KEYS | VALID_TABLES)
    _validate_known_tables(toml, "TOML specification", VALID_TABLES)

    schema_version = _get_schema_version(toml)
    workload_name = _get_workload_name(toml)
    capabilities = _get_capabilities(toml)
    haproxy = _get_haproxy_specfication(toml)
    squid_proxy = _get_squid_proxy_specification(toml)
    ollama_sidecar = _get_ollama_sidecar_specification(toml)
    mcp_sidecar = _get_mcp_sidecar_specification(toml)
    return MetisaSpecification(
        schema_version=schema_version,
        workload_name=workload_name,
        capabilities=capabilities,
        haproxy=haproxy,
        squid_proxy=squid_proxy,
        ollama_sidecar=ollama_sidecar,
        mcp_sidecar=mcp_sidecar
    )


def _get_schema_version(toml: dict[str, object]) -> int:
    schema_version = toml.get("schema_version")

    if schema_version is None:
        error = "TOML specification requires a schema_version integer."
        raise SpecificationValidationError(error)
    
    if not isinstance(schema_version, int):
        error = "TOML specification schema_version must be an integer."
        raise SpecificationValidationError(error)
    
    if isinstance(schema_version, bool): # a boolean passes the previous check
        error = "TOML specification schema_version must be an integer."
        raise SpecificationValidationError(error)
    
    return schema_version


def _get_workload_name(toml: dict[str, object]) -> str:
    workload_name = toml.get("workload_name")

    if workload_name is None:
        error = "TOML specification requires a workload_name string."
        raise SpecificationValidationError(error)
    
    if not isinstance(workload_name, str):
        error = "TOML specification workload_name must be a string."
        raise SpecificationValidationError(error)

    workload_name = workload_name.strip()
    if len(workload_name) == 0:
        error = "TOML specification workload_name must be a non-empty string."
        raise SpecificationValidationError(error)
    
    return workload_name


def _get_capabilities(toml: dict[str, object]) -> frozenset[Capability]:
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


def _get_haproxy_specfication(
    toml: dict[str, object]
) -> HaproxySpecification | None:
    haproxy = toml.get("haproxy")
    if not haproxy:
        return None

    if not isinstance(haproxy, dict):
        raise SpecificationValidationError(
            "TOML specification haproxy must be a table."
        )

    HAPROXY_KEYS = frozenset({
        "ports",
    })

    _validate_known_keys(haproxy, "haproxy", HAPROXY_KEYS)

    ports = _get_int_tuple(haproxy["ports"], "HAProxy ports")

    for port in ports:
        if port < 1:
            raise SpecificationValidationError(
                "TOML specification haproxy ports must be positive integers."
            )

    return HaproxySpecification(ports=ports)


def _get_squid_proxy_specification(
    toml: dict[str, object]
) -> SquidProxySpecification | None:
    squid_proxy = toml.get("squid_proxy")
    if not squid_proxy:
        return None

    if not isinstance(squid_proxy, dict):
        raise SpecificationValidationError(
            "TOML specification squid_proxy must be a table."
        )

    SQUID_PROXY_KEYS = frozenset({
        "allowed_domains",
        "allowed_ip_addresses",
    })

    _validate_known_keys(squid_proxy, "squid_proxy", SQUID_PROXY_KEYS)
    
    allowed_domains = _get_str_tuple(
        squid_proxy.get("allowed_domains"),
        "Squid Proxy allowed domains"
    )

    allowed_ip_addresses = _get_str_tuple(
        squid_proxy.get("allowed_ip_addresses"),
        "Squid Proxy allowed IP addresses"
    )

    return SquidProxySpecification(
        allowed_domains=allowed_domains,
        allowed_ip_addresses=allowed_ip_addresses
    )


def _get_ollama_sidecar_specification(
    toml: dict[str, object]
) -> OllamaSidecarSpecification | None:
    
    ollama_sidecar = toml.get("ollama_sidecar")
    if not ollama_sidecar:
        return None

    if not isinstance(ollama_sidecar, dict):
        raise SpecificationValidationError(
            "TOML specification ollama_sidecar must be a table."
        )

    OLLAMA_KEYS = frozenset({
        "models",
    })

    _validate_known_keys(ollama_sidecar, "ollama_sidecar", OLLAMA_KEYS)

    models = _get_str_tuple(ollama_sidecar["models"], "Ollama models")

    return OllamaSidecarSpecification(models=models)


def _get_mcp_sidecar_specification(
    toml: dict[str, object]
) -> McpSidecarSpecification | None:
    mcp_sidecar = toml.get("mcp_sidecar")
    if not mcp_sidecar:
        return None

    if not isinstance(mcp_sidecar, dict):
        raise SpecificationValidationError(
            "TOML specification mcp_sidecar must be a table."
        )

    MCP_SIDECAR_KEYS = frozenset({
        "tools",
        "resources",
    })

    _validate_known_keys(mcp_sidecar, "mcp_sidecar", MCP_SIDECAR_KEYS)
    
    tools = _get_str_tuple(
        mcp_sidecar.get("tools"),
        "MCP Sidecar allowed domains"
    )

    resources = _get_str_tuple(
        mcp_sidecar.get("resources"),
        "MCP Sidecar allowed IP addresses"
    )

    return McpSidecarSpecification(
        tools=tools,
        resources=resources
    )


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
        f"TOML specification {table_name} contains unknown keys: "
        f"{formatted_keys}."
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


def _get_str_tuple(collection: object | None, section_name: str) -> tuple[str]:
    if not collection:
        return tuple([])
    
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
        trimmed_values.append(trimmed_value)

    return tuple(trimmed_values)


def _get_int_tuple(collection: object | None, section_name: str) -> tuple[int]:
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