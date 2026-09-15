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

- Follow PEP 8 naming: `snake_case` for functions and variables, `PascalCase` for classes, and `UPPER_CASE` for constants.
- Prefix internal functions, classes, modules, and constants with a single leading underscore.
- Treat functions, classes, modules, and constants without a leading underscore as public project API.
- Public modules, classes, and functions should have concise docstrings.
- Use type hints on function and method signatures.
- Do not require type hints for every local variable.
- Prefer small, explicit functions over clever abstractions.
- Prefer one meaningful operation per line. Avoid nesting function calls when naming
  an intermediate value would make the sequence of work clearer.
- Order modules as: docstring, imports, constants, enums, dataclasses/classes, public functions, then private helper functions.
- Within classes, place fields and class variables first, then `__init__`, then public methods and properties, then private helpers.
- When ordering private helper functions, follow call-flow readability when possible.
- Run `.\scripts\check.ps1` after meaningful code changes.
