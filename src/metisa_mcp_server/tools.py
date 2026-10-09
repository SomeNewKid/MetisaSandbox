"""Provide the tools for the Metisa MCP Server."""

from __future__ import annotations

import importlib
import json
import os
from typing import Annotated, Any, TypedDict

from pydantic import Field

_MARIADB_HOST_ENVIRONMENT_VARIABLE = "MARIADB_HOST"
_MARIADB_PORT_ENVIRONMENT_VARIABLE = "MARIADB_PORT"
_MARIADB_DATABASE_ENVIRONMENT_VARIABLE = "MARIADB_DATABASE"
_MARIADB_CREDENTIALS_ENVIRONMENT_VARIABLE = "SANDBOX_TESTER_MARIADB_CREDENTIALS"
_DEFAULT_MARIADB_HOST = "metisa-haproxy"
_DEFAULT_MARIADB_PORT = 3306
_DEFAULT_MARIADB_DATABASE = "agent_allowed"
_ACTIVE_ITEMS_QUERY = """
SELECT id, item_key, title, status, notes, quantity, created_at, updated_at
FROM items
WHERE status = 'active'
ORDER BY id
"""


class _MariaDBConnectionSettings(TypedDict):
    host: str
    port: int
    user: str
    password: str
    database: str


def test_tool_1() -> str:
    """Return a test response."""
    return "Hello, from test_tool_1."


def test_tool_2(
    name: Annotated[str, Field(description="The name of the user")],
) -> str:
    """Return a test response."""
    if not name:
        return "Hello, from test_tool_2."
    return f"Hello, {name}, from test_tool_2."


def test_tool_3(
    name: Annotated[str, Field(description="The name of the user")],
) -> str:
    """Return a test response."""
    if not name:
        raise ValueError("Name must be provided for test_tool_3.")
    return f"Hello, {name}, from test_tool_3."


def get_active_items() -> str:

    try:
        username, _ = _read_mariadb_credentials()
        if not username:
            raise RuntimeError("Database username missing.")
    except Exception as error:
        raise RuntimeError("Environment variables error: {error}") from error

    try:
        maria_db_host = os.environ.get(
            _MARIADB_HOST_ENVIRONMENT_VARIABLE,
            _DEFAULT_MARIADB_HOST,
        )
        return _get_active_items(maria_db_host)
    except Exception as error:
        raise RuntimeError(f"Database connection error: {error}") from error


def _get_active_items(
    maria_db_host: str,
) -> str:
    connection_settings = _read_mariadb_connection_settings(maria_db_host)
    connection = _connect_to_mariadb(connection_settings)
    try:
        with connection.cursor() as cursor:
            cursor.execute(_ACTIVE_ITEMS_QUERY)
            rows = cursor.fetchall()
    finally:
        connection.close()

    normalized_rows = [_normalize_database_row(row) for row in rows]
    return json.dumps(normalized_rows, sort_keys=True, default=str)


def _read_mariadb_connection_settings(
    maria_db_host: str,
) -> _MariaDBConnectionSettings:
    username, password = _read_mariadb_credentials()
    return {
        "host": maria_db_host,
        "port": _read_mariadb_port(),
        "user": username,
        "password": password,
        "database": os.environ.get(
            _MARIADB_DATABASE_ENVIRONMENT_VARIABLE,
            _DEFAULT_MARIADB_DATABASE,
        ),
    }


def _read_mariadb_credentials() -> tuple[str, str]:
    value = os.environ.get(_MARIADB_CREDENTIALS_ENVIRONMENT_VARIABLE)
    if value is None:
        raise RuntimeError(
            f"{_MARIADB_CREDENTIALS_ENVIRONMENT_VARIABLE} is not configured."
        )

    username, separator, password = value.partition(",")
    if not separator or not username.strip() or not password:
        raise RuntimeError(
            f"{_MARIADB_CREDENTIALS_ENVIRONMENT_VARIABLE} must use "
            "the format 'username,password'."
        )

    return username.strip(), password


def _read_mariadb_port() -> int:
    value = os.environ.get(_MARIADB_PORT_ENVIRONMENT_VARIABLE)
    if value is None:
        return _DEFAULT_MARIADB_PORT

    try:
        port = int(value)
    except ValueError as error:
        raise RuntimeError("MARIADB_PORT must be an integer TCP port.") from error

    if port < 1 or port > 65535:
        raise RuntimeError("MARIADB_PORT must be between 1 and 65535.")

    return port


def _connect_to_mariadb(connection_settings: _MariaDBConnectionSettings) -> Any:
    pymysql: Any = importlib.import_module("pymysql")

    return pymysql.connect(
        host=connection_settings["host"],
        port=connection_settings["port"],
        user=connection_settings["user"],
        password=connection_settings["password"],
        database=connection_settings["database"],
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )


def _normalize_database_row(row: object) -> dict[str, object]:
    if isinstance(row, dict):
        return dict(row)

    raise RuntimeError("MariaDB query returned an unexpected row shape.")