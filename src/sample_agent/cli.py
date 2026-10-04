"""Command-line interface for the application."""

from __future__ import annotations

import importlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

import requests

IS_INTERACTIVE = False

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


def main(
    argv: list[str] | None = None,
) -> int:
    """Run the sample agent workload."""
    output_dir = os.environ.get("SANDBOX_OUTPUT_DIR", "")
    is_running_local = not output_dir
    if is_running_local:
        output_dir = _create_run_directory()
    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)

    if IS_INTERACTIVE:
        user_name = input("What is your name? ")
    else:
        user_name = "Fred"

    message = f"Hello {user_name} from the Sample Agent."

    answer_path = output_directory / "answer.txt"
    answer_path.write_text(
        message,
        encoding="utf-8",
    )

    print(message)
    print(f"Wrote answer to {answer_path}")

    url = "https://example.com"
    try:
        response = requests.get(url)
        status_code = response.status_code
        if status_code == 200:
            html = response.text
            if html:
                title = _get_title_from_html(response.text)
                if title:
                    print(f"example.com page title: {title}")
                else:
                    print("Could not get example.com page title.")
            else:
                print("Received empty response.")
        else:
            print(f"Failed to get response.  Status code: {status_code}")
    except Exception as error:
        print("Internet connection exception", error)

    try:
        username, _ = _read_mariadb_credentials()
        if username:
            print("Database username:", username)
        else:
            print("Database username missing.")
    except Exception as error:
        print("Environment variables error:", error)

    try:
        maria_db_host = os.environ.get(
            _MARIADB_HOST_ENVIRONMENT_VARIABLE,
            _DEFAULT_MARIADB_HOST,
        )
        if is_running_local:
            maria_db_host = "localhost"
        active_items = _get_active_items(maria_db_host)
        if active_items:
            print("Database records:", active_items)
        else:
            print("Database records not available.")
    except Exception as error:
        print("Database connection error:", error)

    return 0


# This function is only used when the agent is run without the sandbox.
def _create_run_directory() -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    run_directory = Path.cwd() / ".runs" / f"run-{timestamp}" / "output"
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_directory


def _get_title_from_html(
    html: str,
) -> str:
    tag = "title"
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    open_tag_index = html.find(open_tag)
    close_tag_index = html.find(close_tag)
    if open_tag_index < 0 or close_tag_index < 0:
        return ""
    return html[open_tag_index + len(open_tag) : close_tag_index]


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
