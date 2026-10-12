"""Provide the tools for the Metisa MCP Server."""

from __future__ import annotations

import importlib
import json
import os
import traceback
from typing import Annotated, Any, TypedDict

import requests
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
    """Return the active items from the database."""
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


def get_title_from_url(
    url: Annotated[str, Field(description="The URL endpoint.")],
) -> str | None:
    """Return the title of the document at the specified URL."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return _parse_html_title(response.text)
    except Exception as error:
        raise RuntimeError(f"Could not get title from URL: {error}") from error


def read_content_from_url(
    url: Annotated[str, Field(description="The URL endpoint.")],
) -> str | None:
    """Return plain text from a URL through the Jina Reader sidecar."""
    reader_endpoint = "http://metisa-jina-reader:8081/"
    headers = {
        "Accept": "text/plain",
        "X-Respond-With": "text",
        "X-Engine": "browser",
    }
    payload = {"url": url}

    try:
        with requests.Session() as session:
            print(f"Debug 1: '{url}'")
            session.trust_env = False
            response = session.post(
                reader_endpoint,
                data=payload,
                headers=headers,
                timeout=(5, 60),
            )
            print(f"Debug 2: {response.status_code}")
            response.raise_for_status()
            print("Debug 3")
            content = response.text
            print("Debug 4", str(len(content)))
        return content
    except requests.RequestException as error:
        traceback.print_exception(error)
        error_message = f"Jina Reader could not read the url: {error}"
        raise RuntimeError(error_message) from error
    except Exception as error:
        traceback.print_exception(error)
        error_message = f"Jina Reader could not read the url: {error}"
        raise RuntimeError(error_message) from error


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


def _parse_html_title(response_text: str | None) -> str:
    if not response_text:
        return ""
    open_tag = "<title"
    open_tag_start = response_text.find(open_tag)
    if open_tag_start < 0:
        return ""
    open_tag_end = response_text.find(">", open_tag_start)
    if open_tag_end < 0:
        return ""
    close_tag = "</title>"
    close_tag_start = response_text.find(close_tag, open_tag_end)
    if close_tag_start < 0:
        return ""
    return response_text[open_tag_end + 1 : close_tag_start].strip()
