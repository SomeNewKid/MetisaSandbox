# Agent Instructions

## project Purpose

The goal of the project is for an AI agent workload to use a TOML file to declare its requirements, and for the `MetisaSandbox` application to create a Docker-based hardened sandbox in which to run the AI agent.  By default the sandbox will be temporary and will be torn down after the AI agent has completed its workload.

## Project Guide

While the goal of the project is to produce a Docker-based sandbox in which to run an AI agent workload, the real purpose is for the human developer to learn about Docker networking, Docker containers, and Linux hardening.  For this reason, the application should favor explicit `docker` CLI commands and avoid Docker SDK, Compose, Kubernetes, or hidden framework magic.  The same explicit approach should be taken when configuring the Linux-based containers.

## Project Files

The roadmap for the project is available in the `.\.docs\ROADMAP.md` file.  This is merely a starting roadmap, and is intended as a guide and not as a constraint.

## Codex Purpose

Codex should not create or edit any files, so that the human developer has the opportunity to learn by writing all th code.  The only exception is when the human developer has a problem which he cannot solve, in which case Codex should first perform diagnostic steps so that the code fix is still written by the human developer, and only if the human developer then asks for Codex to make the code fix should Codex create or edit files.

## Python Style

### Package Boundaries and Public Interfaces

- Each immediate child directory of `src` containing `__init__.py` defines a
  top-level project package.
- Nested subpackages remain within their owning top-level package's boundary.
- Public interfaces are those intended for use by another top-level project
  package, whether through imports or direct process invocation.
- An existing cross-package reference does not automatically make an interface
  public. References to private interfaces should prompt a design review.

### Naming and Visibility

- Follow PEP 8 naming: `snake_case` for packages, modules, functions, and
  variables; `PascalCase` for classes; and `UPPER_CASE` for constants.
- Prefix internal packages, modules, classes, functions, and constants with a
  single leading underscore.
- Explicitly prefix internal modules with an underscore even when their
  containing package already has an underscore.
- Packages and modules without a leading underscore represent supported public
  project interfaces, except for Python-defined special filenames.
- Within a public module, use names without a leading underscore for its
  supported interface and underscore-prefixed names for implementation details.
- Within a private module, names without a leading underscore may be used for
  interfaces intended for other modules within the owning top-level package.
  Prefix helpers intended only for use within that module with an underscore.
- An interface remains private when any containing package or module is private.
- Preserve Python-defined special filenames such as `__init__.py` and
  `__main__.py`.

### Entry Points

- A module directly invoked by another top-level package is a public entry
  point, even if no other package imports its functions or classes.
- Use descriptive public entry-point names such as `server.py` where callers
  explicitly invoke that module.
- When callers invoke a package using `python -m package_name`, keep
  `__main__.py` small and delegate to an appropriately named implementation
  module.
- Use descriptive private implementation names such as `_bootstrap.py` for
  initialization and handoff, or `_runner.py` for execution orchestration.
- Reserve `cli.py` for an intentionally user-facing command-line interface.
- Do not add `__main__.py` unless direct execution of the package is supported.

### Documentation and Structure

- Public packages, modules, classes, and functions should have concise docstrings
  describing their purpose.
- Use type hints on function and method signatures.
- Do not require type hints for every local variable.
- Prefer small, explicit functions over clever abstractions.
- Prefer one meaningful operation per line. Avoid nesting function calls when
  naming an intermediate value would make the sequence of work clearer.
- Order modules as: docstring, imports, constants, enums, dataclasses/classes,
  public functions, then private helper functions.
- Within classes, place fields and class variables first, then `__init__`, then
  public methods and properties, then private helpers.
- When ordering private helper functions, follow call-flow readability when
  possible.
- Run `.\scripts\check.ps1` after meaningful code changes.