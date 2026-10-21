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

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                reader_endpoint,
                data=payload,
                headers=headers,
                timeout=(5, 60),
            )
            content = response.text
            response.raise_for_status()
        return content
    except requests.RequestException as error:
        error_message = f"Jina Reader could not read the url: {error}"
        raise RuntimeError(error_message) from error
    except Exception as error:
        traceback.print_exception(error)
        error_message = f"Jina Reader could not read the url: {error}"
        raise RuntimeError(error_message) from error


def classify_text(
    text: Annotated[str, Field(description="The text to classify")],
) -> str | None:
    """Return the classificatin of the provided text."""
    prompt_guard_endpoint = "http://metisa-prompt-guard:8000/classify"
    headers = {
        "Accept": "application/json",
    }
    payload = {"text": text}

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                prompt_guard_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Prompt Guard did not return any content")
        return content
    except Exception as error:
        if content:
            raise RuntimeError(f"Prompt Guard returned an error: {content}") from error
        raise RuntimeError(f"Prompt Guard returned an error: {error}") from error


def moderate_text(
    text: Annotated[str, Field(description="The text to moderate")],
) -> str | None:
    """Return the classificatin of the provided text."""
    prompt_guard_endpoint = "http://metisa-prompt-guard:8000/moderate"
    headers = {
        "Accept": "application/json",
    }
    payload = {"text": text}

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                prompt_guard_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Prompt Guard did not return any content")
        return content
    except Exception as error:
        if content:
            raise RuntimeError(f"Prompt Guard returned an error: {content}") from error
        raise RuntimeError(f"Prompt Guard returned an error: {error}") from error


def anonymize_text(
    text: Annotated[str, Field(description="The text to anonymize")],
) -> str | None:
    """Return the provided text with entities anonymized."""
    entity_guard_endpoint = "http://metisa-entity-guard:8000/anonymize"
    headers = {
        "Accept": "application/json",
    }
    payload = {"text": text}

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                entity_guard_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Entity Guard did not return any content")
        return content
    except Exception as error:
        if content:
            raise RuntimeError(f"Entity Guard returned an error: {content}") from error
        raise RuntimeError(f"Entity Guard returned an error: {error}") from error


def extract_markdown_from_document(
    filename: Annotated[str, Field(description="The filename of the sample.")],
) -> str | None:
    """Return the data from the specified example filename."""
    docling_endpoint = "http://metisa-docling:8000/extract-markdown-from-document"
    headers = {
        "Accept": "application/json",
    }
    payload = {"filename": filename}

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                docling_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Docling did not return any content")
        return content
    except Exception as error:
        if content:
            raise RuntimeError(f"Docling returned an error: {content}") from error
        raise RuntimeError(f"Docling returned an error: {error}") from error


def retrieve_from_documents(
    filename: Annotated[str, Field(description="The filename of the document.")],
) -> str | None:
    """Return the data from the specified filename."""
    documents_endpoint = "http://metisa-documents:8080/"
    document_endpoint = f"{documents_endpoint}{filename}"
    headers = {}

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.get(
                document_endpoint,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Documents did not return any content")
        return content
    except Exception as error:
        if content:
            raise RuntimeError(f"Documents returned an error: {content}") from error
        raise RuntimeError(f"Documents returned an error: {error}") from error


def get_matching_chunks(
    filename: Annotated[str, Field(description="The filename of the document.")],
    prompt: Annotated[str, Field(description="The user's prompt.")],
) -> str | None:
    """Return the data from the specified filename."""
    embeddings_endpoint = "http://metisa-embeddings:8000/search"
    headers = {
        "Accept": "application/json",
    }
    payload = {
        "filename": filename,
        "prompt": prompt,
    }

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                embeddings_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Embeddings did not return any content")
        return content
    except Exception as error:
        if content:
            raise RuntimeError(f"Embeddings returned an error: {content}") from error
        raise RuntimeError(f"Embeddings returned an error: {error}") from error


def execute_starlark_code(
    starlark_code: Annotated[
        str,
        Field(
            description="""
        The Starlark code to be executed, 
        which must reside in a main() function with no parameters.
        For example:
        
        def main():
            values = [10, 20, 30]
            total = 0
            for value in values:
                total += value
            return total / len(values)
        """
        ),
    ],
) -> str | None:
    """Return the result of executing the provided Starlark code."""
    starlark_endpoint = "http://metisa-code-execution:8090/execute"
    headers = {
        "Accept": "application/json",
    }
    payload = {"code": starlark_code}

    content: str | None = None

    trust_env = False  # Private-network requests must bypass the internet proxy.

    try:
        with requests.Session() as session:
            session.trust_env = trust_env
            response = session.post(
                starlark_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 120),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Starlark did not return any content.")
        try:
            dictionary = json.loads(content)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Starlark returned an error: {content}") from error
        if not isinstance(dictionary, dict):
            raise RuntimeError("Starlark did not return expected JSON dictionary.")
        error_result = dictionary.get("error", None)
        if error_result is not None:
            raise RuntimeError(f"Starlark returned an error: {error_result}")
        result = dictionary.get("result", None)
        if result is None:
            raise RuntimeError("Starlark did not return expected JSON format.")
        if not isinstance(result, str):
            raise RuntimeError("Starlark did not return a string result.")
        return result
    except Exception as error:
        if content:
            raise RuntimeError(f"Starlark returned an error: {content}") from error
        raise RuntimeError(f"Starlark returned an error: {error}") from error


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
