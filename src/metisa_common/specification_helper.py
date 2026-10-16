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
    CodeExecutionSpecification,
    HaproxyBackend,
    HaproxySpecification,
    JinaReaderSpecification,
    LlmBrokerSpecification,
    LlmModel,
    LlmServerSpecification,
    McpServerSpecification,
    MetisaSpecification,
    SpecificationValidationError,
    SquidProxySpecification,
)
from .specification_validator import (
    validate_specification,
)

_IMAGE_FORMAT_VERSION = 1
_WORKLOAD_IMAGE_FORMAT_VERSION = 2
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

    # Rebuild cached workload images when their trusted runtime components change.
    ordered_collections.append(f"workload-format-{_WORKLOAD_IMAGE_FORMAT_VERSION}")
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


def alias_is_valid(
    alias: str,
) -> bool:
    """Validate if a string is a valid within a network alias or hostname."""
    # Based on RFC 1123 (DNS-compatible service discovery)
    # but not an RFC 1123 validator.
    if not alias or not isinstance(alias, str):
        return False

    if len(alias) > 52:  # normally limit is 253, but use here is a short alias
        return False

    # Ensure it's not a plain IPv4 address to avoid routing confusion
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", alias):
        return False

    # Regex rule per label (RFC 1123):
    # - Must be between 1 and 63 characters long
    # - Can contain lowercase/uppercase letters, digits, and hyphens
    # - Must start and end with an alphanumeric character (letter or digit)
    if not re.match(r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?$", alias):
        return False

    return True


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
        name, value = _get_environ_name_value(environ)
    except ValueError:
        return False

    if _environ_name_is_reserved(name):
        return False

    if not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", name):
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


def get_resolved_environs_for_metisa(
    specification: MetisaSpecification,
) -> list[str]:
    """Resolve environment variables specified for the Metisa workload container."""
    return _get_resolved_environs(specification.environs)


def get_resolved_environs_for_mcp_server(
    specification: MetisaSpecification,
) -> list[str]:
    """Resolve environment variables specified for the MCP server container."""
    if not specification.mcp_server:
        return []
    if not specification.mcp_server.environs:
        return []
    return _get_resolved_environs(specification.mcp_server.environs)


def get_resolved_environs_for_llm_broker(
    specification: MetisaSpecification,
) -> list[str]:
    """Resolve environment variables specified for the LLM Broker container."""
    if not specification.llm_broker:
        return []
    if not specification.llm_broker.environs:
        return []
    return _get_resolved_environs(specification.llm_broker.environs)


def get_resolved_environs_for_jina_reader(
    specification: MetisaSpecification,
) -> list[str]:
    """Resolve environment variables specified for the Jina Reader container."""
    if not specification.jina_reader:
        return []
    if not specification.jina_reader.environs:
        return []
    return _get_resolved_environs(specification.jina_reader.environs)


def get_resolved_environs_for_code_execution(
    specification: MetisaSpecification,
) -> list[str]:
    """Resolve environment variables specified for the Code Execution container."""
    if not specification.code_execution:
        return []
    if not specification.code_execution.environs:
        return []
    return _get_resolved_environs(specification.code_execution.environs)


def _get_resolved_environs(
    environs: frozenset[str],
) -> list[str]:
    resolved_list: list[str] = []

    for environ in environs:
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
            "settings",
        }
    )

    VALID_TABLES = frozenset(
        {
            "squid_proxy",
            "haproxy",
            "llm_broker",
            "llm_server",
            "mcp_server",
            "jina_reader",
            "code_execution",
        }
    )

    _validate_known_keys(toml, "TOML specification", VALID_KEYS | VALID_TABLES)
    _validate_known_tables(toml, "TOML specification", VALID_TABLES)

    agent_name = _get_agent_name(toml)
    capabilities = _get_capabilities(toml)
    dependencies = _get_dependencies(toml)
    environs = _get_environs(toml, "TOML specification environs")
    settings = _get_settings(toml)
    haproxy = _get_haproxy_specfication(toml)
    squid_proxy = _get_squid_proxy_specification(toml)
    llm_server = _get_llm_server_specification(toml)
    llm_broker = _get_llm_broker_specification(toml)
    mcp_server = _get_mcp_server_specification(toml)
    jina_reader = _get_jina_reader_specification(toml)
    code_execution = _get_code_execution_specification(toml)
    specification = MetisaSpecification(
        agent_name=agent_name,
        capabilities=capabilities,
        dependencies=dependencies,
        environs=environs,
        settings=settings,
        haproxy=haproxy,
        squid_proxy=squid_proxy,
        llm_server=llm_server,
        llm_broker=llm_broker,
        mcp_server=mcp_server,
        jina_reader=jina_reader,
        code_execution=code_execution,
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


def _get_settings(
    toml: dict[str, object],
) -> dict[str, str]:
    raw_settings = _get_str_tuple(toml.get("settings"), "TOML specification settings")

    keys: list[str] = []
    settings: dict[str, str] = {}

    for raw_setting in raw_settings:
        parts = raw_setting.split("=")
        if len(parts) != 2:
            raise SpecificationValidationError(
                f"TOML specification setting '{raw_setting}' is invalid supported."
            )
        key = parts[0].strip()
        if key in keys:
            raise SpecificationValidationError(
                f"TOML specification setting has duplicate keys: '{key}'."
            )
        value = parts[1].strip()
        keys.append(key)
        settings[key] = value

    return settings


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
    source: str,
) -> frozenset[str]:
    raw_environs = _get_str_tuple(toml.get("environs"), source)

    environs: set[str] = set()

    for raw_environ in raw_environs:
        if not isinstance(raw_environ, str):
            raise SpecificationValidationError(
                f"TOML specification environ '{raw_environ}' is not supported."
            )
        if _environ_is_reserved(raw_environ):
            raise SpecificationValidationError(
                f"TOML specification environ '{raw_environ}' is not permitted."
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
                error = "HAProxy backends must be an array of objects"
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


def _get_llm_server_specification(
    toml: dict[str, object],
) -> LlmServerSpecification | None:

    llm_server = toml.get("llm_server")
    if not llm_server:
        return None

    if not isinstance(llm_server, dict):
        raise SpecificationValidationError(
            "TOML specification llm_server must be a table."
        )

    LLM_SERVER_KEYS = frozenset(
        {
            "models",
        }
    )

    _validate_known_keys(llm_server, "llm_server", LLM_SERVER_KEYS)

    models: list[LlmModel] = []

    raw_models = llm_server.get("models", [])
    if raw_models is not None:
        if isinstance(raw_models, str):
            raise SpecificationValidationError("LLM server models must be an array.")
        if not isinstance(raw_models, list):
            raise SpecificationValidationError("LLM server models must be an array.")

        for raw_model in raw_models:
            if not isinstance(raw_model, dict):
                error = "LLM server model must be an array of objects."
                raise SpecificationValidationError(error)

            model = _get_llm_model(raw_model)
            if model in models:
                error = (
                    "Duplicate LLM server model: "
                    f"repo={model.repo}, "
                    f"revision={model.revision}, "
                    f"filename={model.filename}."
                )
                raise SpecificationValidationError(error)

            if any(existing.alias == model.alias for existing in models):
                error = f"Duplicate LLM server model alias: '{model.alias}'"
                raise SpecificationValidationError(error)

            models.append(model)

    return LlmServerSpecification(models=tuple(models))


def _get_llm_model(
    definition: dict[str, object],
) -> LlmModel:
    alias = definition.get("alias")
    if not alias:
        error = "LLM model must specify an alias."
        raise SpecificationValidationError(error)
    if not isinstance(alias, str):
        error = "LLM model must specify a string alias."
        raise SpecificationValidationError(error)
    if not alias_is_valid(alias):
        error = f"LLM model alias not valid: '{alias}'."
        raise SpecificationValidationError(error)

    repo = definition.get("repo")
    if not repo:
        error = "LLM model must specify a repo."
        raise SpecificationValidationError(error)
    if not isinstance(repo, str):
        error = "LLM model must specify a string repo."
        raise SpecificationValidationError(error)

    revision = definition.get("revision")
    if not revision:
        error = "LLM model must specify a revision."
        raise SpecificationValidationError(error)
    if not isinstance(revision, str):
        error = "LLM model must specify a string revision."
        raise SpecificationValidationError(error)

    filename = definition.get("filename")
    if not filename:
        error = "LLM model must specify a filename."
        raise SpecificationValidationError(error)
    if not isinstance(filename, str):
        error = "LLM model must specify a string filename."
        raise SpecificationValidationError(error)

    return LlmModel(alias, repo, revision, filename)


def _get_mcp_server_specification(
    toml: dict[str, object],
) -> McpServerSpecification | None:
    mcp_server = toml.get("mcp_server")
    if not mcp_server:
        return None

    if not isinstance(mcp_server, dict):
        raise SpecificationValidationError(
            "TOML specification mcp_server must be a table."
        )

    MCP_SERVER_KEYS = frozenset(
        {
            "tools",
            "resources",
            "environs",
        }
    )

    _validate_known_keys(mcp_server, "mcp_server", MCP_SERVER_KEYS)

    tools = _get_str_tuple(mcp_server.get("tools"), "MCP Server tools")

    resources = _get_str_tuple(mcp_server.get("resources"), "MCP Server resources")

    environs = _get_environs(mcp_server, "MCP Server environs")

    return McpServerSpecification(tools=tools, resources=resources, environs=environs)


def _get_llm_broker_specification(
    toml: dict[str, object],
) -> LlmBrokerSpecification | None:
    llm_broker = toml.get("llm_broker")
    if not llm_broker:
        return None

    if not isinstance(llm_broker, dict):
        raise SpecificationValidationError(
            "TOML specification llm_broker must be a table."
        )

    LLM_BROKER_KEYS = frozenset(
        {
            "environs",
            "local_models",
            "online_models",
        }
    )

    _validate_known_keys(llm_broker, "LLM Broker", LLM_BROKER_KEYS)

    environs = _get_environs(llm_broker, "LLM Broker environs")

    local_models = _get_str_tuple(
        llm_broker.get("local_models"), "LLM Broker local models"
    )
    online_models = _get_str_tuple(
        llm_broker.get("online_models"), "LLM Broker online models"
    )

    return LlmBrokerSpecification(
        environs=environs, local_models=local_models, online_models=online_models
    )


def _get_jina_reader_specification(
    toml: dict[str, object],
) -> JinaReaderSpecification | None:
    jina_reader = toml.get("jina_reader")
    if not jina_reader:
        return None

    if not isinstance(jina_reader, dict):
        raise SpecificationValidationError(
            "TOML specification jina_reader must be a table."
        )

    JINA_READER_KEYS = frozenset(
        {
            "environs",
        }
    )

    _validate_known_keys(jina_reader, "jina_reader", JINA_READER_KEYS)

    environs = _get_environs(jina_reader, "Jina Reader environs")

    return JinaReaderSpecification(environs=environs)


def _get_code_execution_specification(
    toml: dict[str, object],
) -> CodeExecutionSpecification | None:
    code_execution = toml.get("code_execution")
    if not code_execution:
        return None

    if not isinstance(code_execution, dict):
        raise SpecificationValidationError(
            "TOML specification code_execution must be a table."
        )

    CODE_EXECUTION_KEYS = frozenset(
        {
            "environs",
        }
    )

    _validate_known_keys(code_execution, "code_execution", CODE_EXECUTION_KEYS)

    environs = _get_environs(code_execution, "Code Execution environs")

    return CodeExecutionSpecification(environs=environs)


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


def _environ_is_reserved(
    environ: str,
) -> bool:
    """Validate the TOML environ value."""
    try:
        name, _ = _get_environ_name_value(environ)
    except ValueError:
        return False
    return _environ_name_is_reserved(name)


def _environ_name_is_reserved(
    name: str,
) -> bool:
    name = name.upper()

    # The sandbox launcher owns startup roles and output paths.
    reserved_by_metisa = (
        "METISA_RUNTIME_ROLE",
        "SANDBOX_OUTPUT_DIR",
    )
    if name in reserved_by_metisa:
        return True

    # Container managers own proxy configuration.
    # Reserve them even when internet access is disabled.
    reserved_proxy_names = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
    )
    if name in reserved_proxy_names:
        return True

    # Dynamic-loader settings can affect execution before Python’s guards start.
    if name.startswith("LD_"):
        return True

    # Prevent declarations from changing executable lookup or interpreter configuration.
    if name == "PATH" or name.startswith("PYTHON"):
        return True

    # Keep configuration, persistence, and temporary-file locations
    # under sandbox control.
    configuration_names = (
        "HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_RUNTIME_DIR",
        "GNUPGHOME",
        "TMPDIR",
        "TMP",
        "TEMP",
    )
    if name in configuration_names:
        return True

    integration_channels = (
        "SSH_AUTH_SOCK",
        "GPG_AGENT_INFO",
        "DBUS_SESSION_BUS_ADDRESS",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
    )
    if name in integration_channels:
        return True

    return False
