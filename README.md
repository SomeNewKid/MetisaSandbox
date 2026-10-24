# Metisa Sandbox

Metisa Sandbox is a Python command-line application that runs Python agent
workloads inside temporary, hardened Linux containers. Each workload declares
its requirements in a `metisa.toml` file. The application builds or reuses Docker
images, provisions the requested services, checks the sandbox's restrictions,
runs the workload, and tears down its containers and networks afterward.

The project is also a practical exercise in Docker networking, container
isolation, and Linux hardening. It uses explicit `docker` CLI commands rather
than the Docker SDK, Docker Compose, or an orchestration framework.

> [!WARNING]
> This is an experimental AI agent sandboxing project. It is a
> learning and hardening exercise, not a finished security model.

## Features

- Declarative workload configuration, including capabilities, dependencies,
  environment variables, secrets, and service settings.
- Separate workload, backend, and egress networks, created as required.
- Controlled internet access through Squid and configured local network access
  through HAProxy.
- Optional MCP tools, local and online language models, document processing,
  semantic retrieval, text guards, and Starlark execution.
- Container hardening, a custom workload seccomp profile, Landlock filesystem
  restrictions, and Python runtime guards.
- Security probes that must pass before the workload starts.
- Per-run output and logs, with automatic cleanup of temporary resources.

## Requirements

- **Windows and PowerShell.** The host implementation uses Windows-specific
  terminal and Docker Desktop integration.
- **Python 3.11 or later.** The project metadata requires Python 3.11+; Python
  container images currently use Python 3.12.
- **Docker Desktop running Linux containers**, with the `docker` command on
  `PATH` and support for BuildKit named build contexts and build mounts.
- **A Linux container kernel with Landlock support.** The workload bootstrap
  stops if it cannot apply its restrictions.
- Network access for installing dependencies, pulling images, and downloading
  models used during some service image builds. Runtime internet access is
  separately controlled by the workload specification.

Service-heavy workloads require additional memory, disk space, and model files.
The included sample enables most services and needs preparation described below.

## Installation

Run these commands from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --editable ".[dev]"
```

The `dev` extra installs Ruff, Pyright, and pytest. Omit `[dev]` if development
tools are not needed. Installation includes the project's machine learning and
document-processing dependencies and may take some time.

An existing setup script provides the same development installation:


```powershell
.\scripts\setup-dev.ps1
```

That script currently contains a developer-specific absolute Python path. Use
the manual commands above on another machine, or adjust the script's
`$HostPython` value for your installation.

Keep the checkout available: runtime provisioning reads source files and
Dockerfiles from the repository. Run the application from the repository root.

## Usage

Pass the name of a workload package located under `src`:

```powershell
.\.venv\Scripts\python.exe -m metisa_sandbox sample_agent
```

After activating the virtual environment, the installed console entry point is
also available:

```powershell
.\.venv\Scripts\Activate.ps1
metisa-sandbox sample_agent
```

The argument identifies a Python package containing `metisa.toml` and an
executable `__main__.py`. It is not a prompt identifier or a configuration path.
If Docker Engine is unavailable, the application offers to start Docker Desktop.
Images are built when the required image reference does not already exist.

The CLI returns the workload's exit status, or a nonzero status when setup or
the pre-workload security probes fail.

### Create a minimal workload

For a workload without runtime networking or optional services, create:

```text
src/
└── hello_agent/
    ├── __init__.py
    ├── __main__.py
    └── metisa.toml
```

Leave `__init__.py` empty. In `metisa.toml`, declare:

```toml
agent_name = "hello_agent"
capabilities = []
dependencies = []
environs = []
secrets = []
settings = []
```

In `__main__.py`, write an output file using the supplied output directory:

```python
"""Write a greeting from inside the sandbox."""

import os
from pathlib import Path

output_directory = Path(os.environ["SANDBOX_OUTPUT_DIR"])
output_file = output_directory / "greeting.txt"
output_file.write_text("Hello from Metisa Sandbox!\n", encoding="utf-8")
print("Wrote greeting.txt")
```

Run it with:

```powershell
.\.venv\Scripts\python.exe -m metisa_sandbox hello_agent
```

Docker image construction still needs its build dependencies; an empty
capability list disables workload networking at runtime.

## Workload configuration

See [the sample specification](src/sample_agent/metisa.toml) for a configuration
that enables most services. The parser and validation rules are implemented in
[`metisa_common`](src/metisa_common).

### Top-level fields

| Field | Purpose |
| --- | --- |
| `agent_name` | Required, nonempty workload name. The CLI argument selects the package to execute. |
| `capabilities` | Array of capabilities requested by the workload. |
| `dependencies` | Python package requirements installed into the workload image. |
| `environs` | Environment declarations in `NAME=value` form. |
| `secrets` | Secret declarations in `NAME=value` form, provisioned separately from environment variables. |
| `settings` | Application settings in `name=value` form, including `local_models_directory`. |

Dependency declarations currently accept package names with `==`, `>=`, or `~=`
and numeric versions, such as `requests==2.34.2`. They do not support every form
of pip requirement, such as URLs, extras, or compound version constraints.

Environment variables and secrets can resolve values from the host process:

```toml
environs = ["AGENT_LABEL=${host:AGENT_LABEL}"]
secrets = ["SERVICE_TOKEN=${host:SERVICE_TOKEN}"]
```

Set the referenced variables in the PowerShell session used to launch the
sandbox. The application does not automatically load a `.env` file. Use host
references for credentials rather than committing credential values in TOML.

### Capabilities and services

| Capability | Behavior |
| --- | --- |
| `network` | Connects the workload to an internal Docker network; otherwise it uses `--network none`. |
| `internet` | Creates Squid-controlled egress using `[squid_proxy]` domain and IP allowlists. Requires `network`. |
| `localnet` | Creates HAProxy routes to the destinations in `[haproxy].backends`. Requires `network`. |
| `mcp_server` | Provides the tools and resources selected in `[mcp_server]`. Requires `network`, `prompt_guard`, and `entity_guard`. |
| `prompt_guard` | Provides prompt injection checks and text moderation. Started alongside MCP or the LLM broker. |
| `entity_guard` | Provides entity detection and anonymization. Started alongside MCP or the LLM broker. |
| `jina_reader` | Provides web content extraction through Jina Reader. Requires `mcp_server`. |
| `code_execution` | Provides Starlark execution in a separate Go service. Requires `mcp_server`. |
| `llm_server` | Runs a llama.cpp container for each model in `[llm_server].models`. Requires `network`; use with the broker for workload access. |
| `llm_broker` | Routes requests to configured local model aliases and online OpenAI models. Requires `network`, `prompt_guard`, and `entity_guard`. |
| `documents` | Serves files staged from `[documents].local_directory` through Nginx. |
| `docling` | Converts documents to Markdown and chunks. Requires `mcp_server` and `documents`. |
| `qdrant` | Provides a vector database for retrieval. |
| `embeddings` | Indexes document chunks and searches for matching content using Qdrant. Requires `docling`; include `qdrant` for storage. |
| `otel_collector` | Collects OpenTelemetry traces from configured components. |

Include the configuration tables and prerequisite capabilities needed by each
service. Start from a working combination in the sample specification; the
validator does not check every possible service dependency.

For example, controlled internet access can be configured with:

```toml
agent_name = "web_agent"
capabilities = ["network", "internet"]
dependencies = ["requests==2.34.2"]

[squid_proxy]
allowed_domains = [".example.com"]
allowed_ip_addresses = []
```

MCP tools include database queries, URL retrieval, text classification and
moderation, anonymization, Starlark execution, document conversion, and semantic
search. Tools must be explicitly selected in `[mcp_server].tools`.

The LLM broker exposes a restricted, non-streaming subset of the models, chat
completions, and responses APIs. It validates model aliases, request fields,
payload sizes, and response shapes. Streaming, stored responses, and arbitrary
API fields are not supported. Content inspection and transformation in the
broker remain placeholders; enabling the guard services does not automatically
filter every model request or response.

## Running the sample agent

[`sample_agent`](src/sample_agent) exercises the sandbox services, including
network access, database queries, text guards, model requests, documents,
retrieval, secrets, and tracing. It writes `answer.txt` to the run output directory.
It is an integration demonstration rather than a complete autonomous agent.

Before running its checked-in configuration:

1. Review [its TOML file](src/sample_agent/metisa.toml), especially the enabled
   capabilities, local paths, allowed destinations, and credentials.
2. Set `local_models_directory` to your model directory. GGUF files must already
   exist under `<directory>/<repo>/<revision>/<filename>`, matching each entry
   in `[llm_server].models`. The application does not download these files.
3. Provide Prompt Guard model directories beneath the same model directory:

   ```text
   meta-llama/Llama-Prompt-Guard-2-22M/11614a155199674a0a95e6602d6ab0417b790ed0/
   KoalaAI/Text-Moderation/838ade0edb66dcffc5532d08ff6ed5c899abfb5c/
   ```

   These paths are currently fixed in the Prompt Guard container manager.
   Each directory must contain the model and tokenizer files needed to load it
   locally. Obtain any required model access before preparing the files.
4. Set the host variables referenced by the sample:
   `METISA_PROBE_2`, `OPENAI_API_KEY`, and
   `SANDBOX_TESTER_MARIADB_CREDENTIALS`. The MariaDB credential format is
   `username,password`.
5. Provide the MariaDB service configured through HAProxy, or remove the
   corresponding integration capability and configuration. The sample routes
   port 3306 to `host.docker.internal`.
6. Create and populate the configured document directory, currently `.docs`,
   with the files referenced by the sample's document tests. This directory is
   ignored by Git and is not supplied by the checkout.

Some service builds download additional models, including Docling artifacts,
embedding models, and the spaCy model used for anonymization. Expect the first
build to take longer than subsequent runs.

## Architecture

The host CLI loads the specification and creates a unique run context. It uses
explicit Docker commands to build images and create, connect, start, inspect,
stop, and remove containers.

The networking arrangement is:

```text
Workload container
    |
    +-- internal workload network -- MCP server / LLM broker
    |                                      |
    |                              internal backend network
    |                                      |
    |                              supporting services
    |
    +-- configured proxy access -- Squid / HAProxy -- egress network
```

Only the networks and services needed for the configured workload are created.
MCP and the LLM broker bridge the workload and backend networks. Squid handles
permitted internet access; HAProxy handles configured local network routes.
With the LLM broker enabled, the workload is not configured for direct Squid
access. Services communicate through Docker network aliases rather than
published host ports.

Inside the workload container, startup follows this sequence:

```text
Secrets provisioning
    -> Landlock bootstrap
    -> security probes
    -> Python workload package
```

Failed secrets provisioning, Landlock setup, or security probes prevents the
workload from starting.

## Security model

The implementation combines several controls:

- Non-root container identities, dropped Linux capabilities, and
  `no-new-privileges`.
- Read-only root filesystems, read-only workload source mounts, dedicated
  output storage, and restricted memory-backed temporary directories.
- CPU, memory, process, file descriptor, and file size limits, with
  service-specific settings.
- A custom workload seccomp profile and Landlock filesystem allow rules.
- Isolated Python startup, disabled bytecode writes, and runtime guards for
  selected imports, writable code locations, process spawning, sockets, and
  hardware access.
- Runtime probes covering container identity, filesystem and network access,
  Linux capabilities, resource limits, seccomp, Landlock, and Python behavior.
- Encrypted staged secrets, with decryption keys delivered separately through
  stdin to a provisioning process and stored in a restricted tmpfs directory.

This is a learning project under development. These controls and their probes
are not a formal security audit or a guarantee of containment for hostile code.
The host Docker installation, Linux kernel, images, dependencies, and configured
external services remain part of the trusted environment. Build-time dependency
installation is separate from the workload's runtime restrictions.

## Output and cleanup

Runs are stored relative to the directory from which the CLI is launched:

```text
.runs/
└── run-<timestamp>/
    ├── output/       # Workload-generated files
    └── .logs/        # Probe, Landlock, and service logs
```

The workload receives `SANDBOX_OUTPUT_DIR=/sandbox-output` for writing retained
files. Normal cleanup removes containers, networks, staged source and secret
files, and scratch storage, while keeping output and collected logs. Cleanup
also runs when setup or execution raises an error. Docker images remain cached
for reuse.

A forced termination or unavailable Docker daemon can leave resources behind.
Inspect the CLI's cleanup errors and use `docker ps -a` and `docker network ls`
to identify the affected run before removing its resources.

## Development

Install the development dependencies as described above, then run:

```powershell
.\scripts\check.ps1
```

The script runs Ruff formatting, Ruff linting, source docstring checks, Pyright,
and pytest. The formatting step can modify Python files.

To run only unit tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Unit tests cover specification parsing and validation, MCP helpers, and prompt
checks. Container security probes run separately inside each sandbox; the
sample agent provides additional service integration exercises.

### Repository layout

| Path | Contents |
| --- | --- |
| `src/metisa_sandbox/` | Host CLI, Docker helpers, lifecycle management, Dockerfiles, and sidecar provisioning. |
| `src/metisa_common/` | Shared specification, terminal, and secrets utilities. |
| `src/metisa_landlock/` | Linux filesystem restrictions and workload bootstrap. |
| `src/metisa_runner/` | Probe execution and handoff to the workload. |
| `src/metisa_probes/` | Container, kernel, and Python security checks. |
| `src/metisa_mcp_server/` | Configured MCP tools and resources. |
| `src/metisa_llm_broker/` | Restricted local and online model request routing. |
| `src/metisa_prompt_guard/`, `src/metisa_entity_guard/` | Text classification, moderation, and anonymization services. |
| `src/metisa_docling/`, `src/metisa_embeddings/` | Document conversion, indexing, and retrieval services. |
| `src/sample_agent/` | Sample workload, TOML configuration, and service exercises. |
| `tests/` | Unit tests. |
| `scripts/` | PowerShell setup and development checks. |

Follow [AGENTS.md](AGENTS.md) for the project's package boundaries, public
interfaces, naming conventions, and Python style. Keep Docker and Linux
configuration explicit so the implementation remains useful for learning.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Docker command unavailable or Engine unreachable | Check `docker info`, Docker Desktop installation, Linux container mode, and `PATH`. |
| Workload package or specification not found | Run from the repository root with the project's virtual environment; check `src/<package>/metisa.toml`. |
| Invalid specification | Check capability prerequisites, table names, dependency syntax, and environment declarations. |
| Missing host variable | Set the variable referenced by `${host:NAME}` in the launching session. |
| Model file or directory not found | Check `local_models_directory`, exact revisions, filenames, and the fixed Prompt Guard paths. |
| Documents directory not found | Create the configured local directory or change `[documents].local_directory`. |
| Image build fails | Inspect Docker build output, dependency availability, model download access, and disk space. |
| Bootstrap or probes fail | Inspect `.runs/<run>/.logs`, kernel support, and the specific failed restriction or service check. |
| A service is slow or exits unexpectedly | Inspect its logs and Docker resource allocation; models have different memory and startup requirements. |

## License

See [LICENSE](LICENSE) for the GNU General Public License, version 3.
