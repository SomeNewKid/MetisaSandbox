"""Server for the Prompt Guard HTTP endpoints."""

import json
import os
from dataclasses import asdict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import cast
from urllib.parse import urlsplit
from uuid import UUID

import jwt
import psycopg
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from psycopg.conninfo import make_conninfo

from metisa_common.secrets_helper import load_secrets

from ._authentication import get_user_sid
from ._models import Episode, JsonObject, Memory
from ._store import MemoryStore

_MAX_REQUEST_BYTES = 1024 * 1024  # 1 MiB

_EPISODE_REQUIRED = frozenset(
    {
        "kind",
        "content",
    }
)
_EPISODE_OPTIONAL = frozenset(
    {
        "agent_id",
        "run_id",
        "trace_id",
        "metadata",
        "expires_at",
    }
)

_MEMORY_REQUIRED = frozenset(
    {
        "subject",
        "content",
        "text",
        "embedding",
    }
)
_MEMORY_OPTIONAL = frozenset(
    {
        "metadata",
        "valid_to",
        "expires_at",
    }
)


class _RequestError(Exception):
    def __init__(
        self,
        status: HTTPStatus,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.headers = headers if headers is not None else {}


class _DatabaseSettings:
    def __init__(
        self,
    ) -> None:
        self._lock = Lock()
        self._connection_string: str | None = None

    def get_connection_string(
        self,
    ) -> str:
        """Load database credentials once, after provisioning completes."""
        with self._lock:
            if self._connection_string is not None:
                return self._connection_string

            try:
                secrets = load_secrets()
            except FileNotFoundError as error:
                raise _RequestError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "Database credentials are not yet provisioned.",
                    {"Retry-After": "1"},
                ) from error

            password = secrets.get("POSTGRES_PASSWORD")
            if password is None or not password.strip():
                raise ValueError("POSTGRES_PASSWORD secret is required.")

            connection_string = make_conninfo(
                host="metisa-postgres",
                port=5432,
                dbname="agent_memory",
                user="postgres",
                password=password,
            )

            self._connection_string = connection_string
            return connection_string


class _RequestHandler(BaseHTTPRequestHandler):
    # Assigned once during setup; shared configuration is read-only
    _database_settings: _DatabaseSettings
    _run_identifier: str
    _public_key: rsa.RSAPublicKey

    def do_GET(self) -> None:
        self._handle_request()

    def do_POST(self) -> None:
        self._handle_request()

    def do_PUT(self) -> None:
        self._handle_request()

    def do_DELETE(self) -> None:
        self._handle_request()

    def _handle_request(self) -> None:
        self.close_connection = True
        self.connection.settimeout(10)

        try:
            status, payload, headers = self._dispatch()

        except _RequestError as error:
            status = error.status
            payload = {"error": str(error)}
            headers = error.headers

        except TimeoutError:
            status = HTTPStatus.REQUEST_TIMEOUT
            payload = {"error": "Request timed out."}
            headers = {}

        except psycopg.OperationalError:
            status = HTTPStatus.SERVICE_UNAVAILABLE
            payload = {"error": "Database unavailable."}
            headers = {}

        except psycopg.IntegrityError:
            status = HTTPStatus.CONFLICT
            payload = {"error": "The operation conflicts with database constraints."}
            headers = {}

        except psycopg.DataError:
            status = HTTPStatus.UNPROCESSABLE_ENTITY
            payload = {"error": "A supplied value cannot be stored."}
            headers = {}

        except Exception as error:
            # Do not expose database details or credentials to the client.
            self.log_error("Unhandled error: %s", type(error).__name__)
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            payload = {"error": "Internal server error."}
            headers = {}

        self._send_json(status, payload, headers)

    def _dispatch(
        self,
    ) -> tuple[HTTPStatus, object, dict[str, str]]:
        target = urlsplit(self.path)

        if target.query:
            error_message = "URL query parameters are not supported"
            raise _RequestError(HTTPStatus.BAD_REQUEST, error_message)

        if target.fragment:
            error_message = "URL fragment is not supported"
            raise _RequestError(HTTPStatus.BAD_REQUEST, error_message)

        if target.path == "/health":
            self._require_method({"GET"})
            return HTTPStatus.OK, {"status": "healthy"}, {}

        namespace = self._authenticate()
        collection, identifier = self._parse_resource(target.path)

        if identifier is None:
            allowed_methods = {"POST"}
        elif collection == "episodes":
            allowed_methods = {"GET", "DELETE"}
        else:
            allowed_methods = {"GET", "PUT", "DELETE"}

        self._require_method(allowed_methods)

        connection_string = self._database_settings.get_connection_string()
        store = MemoryStore(connection_string, namespace)

        if self.command == "POST":
            payload = self._read_json()

            if collection == "episodes":
                episode = _episode_from_payload(payload, namespace)
                created = store.create_episode(episode)
            else:
                memory = _memory_from_payload(payload, namespace)
                created = store.create_memory(memory)

            location = f"/{collection}/{created.id}"
            return (
                HTTPStatus.CREATED,
                asdict(created),
                {"Location": location},
            )

        # All remaining supported operations require an item ID.
        if identifier is None:
            raise RuntimeError("An item route requires an identifier.")

        if self.command == "GET":
            if collection == "episodes":
                record = store.get_episode(identifier)
            else:
                record = store.get_memory(identifier)

            if record is None:
                raise _RequestError(HTTPStatus.NOT_FOUND, "Record not found.")

            return HTTPStatus.OK, asdict(record), {}

        if self.command == "PUT":
            payload = self._read_json()
            memory = _memory_from_payload(
                payload,
                namespace,
                identifier=identifier,
            )

            try:
                updated = store.update_memory(memory)
            except LookupError as error:
                raise _RequestError(
                    HTTPStatus.NOT_FOUND,
                    "Memory not found.",
                ) from error

            return HTTPStatus.OK, asdict(updated), {}

        if collection == "episodes":
            deleted = store.delete_episode(identifier)
        else:
            deleted = store.delete_memory(identifier)

        if not deleted:
            raise _RequestError(
                HTTPStatus.NOT_FOUND,
                "Record not found.",
            )

        return HTTPStatus.NO_CONTENT, None, {}

    def _authenticate(
        self,
    ) -> str:
        try:
            user_sid = get_user_sid(self, self._public_key, self._run_identifier)
        except jwt.InvalidTokenError as error:
            raise _RequestError(
                HTTPStatus.UNAUTHORIZED,
                "A valid bearer token is required.",
                {"WWW-Authenticate": 'Bearer realm="metisa-agent-memory"'},
            ) from error

        return f"user:{user_sid}"

    def _parse_resource(
        self,
        path: str,
    ) -> tuple[str, UUID | None]:
        parts = path.split("/")

        if (
            len(parts) not in (2, 3)
            or parts[0] != ""
            or parts[1] not in {"episodes", "memories"}
        ):
            raise _RequestError(
                HTTPStatus.NOT_FOUND,
                "Endpoint not found.",
            )

        collection = parts[1]

        if len(parts) == 2:
            return collection, None

        try:
            identifier = UUID(parts[2])
        except ValueError as error:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST,
                "The record ID must be a UUID.",
            ) from error

        return collection, identifier

    def _require_method(
        self,
        allowed: set[str],
    ) -> None:
        if self.command not in allowed:
            raise _RequestError(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "Method not allowed for this endpoint.",
                {"Allow": ", ".join(sorted(allowed))},
            )

    def _read_json(
        self,
    ) -> dict[str, object]:
        if self.headers.get("Transfer-Encoding") is not None:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST,
                "Transfer-Encoding is not supported.",
            )

        encoding = self.headers.get("Content-Encoding", "identity")
        if encoding.lower() != "identity":
            raise _RequestError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "Compressed request bodies are not supported.",
            )

        if self.headers.get_content_type() != "application/json":
            raise _RequestError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "Expected application/json.",
            )

        lengths = self.headers.get_all("Content-Length", [])

        if not lengths:
            raise _RequestError(
                HTTPStatus.LENGTH_REQUIRED,
                "Content-Length is required.",
            )

        if len(lengths) != 1:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST,
                "Expected one Content-Length header.",
            )

        length_text = lengths[0].strip()
        if not length_text.isascii() or not length_text.isdecimal():
            raise _RequestError(
                HTTPStatus.BAD_REQUEST,
                "Invalid Content-Length.",
            )

        length = int(length_text)
        if length > _MAX_REQUEST_BYTES:
            raise _RequestError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "Request body is too large.",
            )

        raw_body = self.rfile.read(length)
        if len(raw_body) != length:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST,
                "Incomplete request body.",
            )

        try:
            text = raw_body.decode("utf-8")
            payload = json.loads(
                text,
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, ValueError, RecursionError) as error:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST,
                "Expected valid UTF-8 JSON.",
            ) from error

        if not isinstance(payload, dict):
            raise _RequestError(
                HTTPStatus.BAD_REQUEST,
                "Expected a JSON object.",
            )

        return cast(dict[str, object], payload)

    def _send_json(
        self,
        status: HTTPStatus,
        payload: object,
        headers: dict[str, str],
    ) -> None:
        if status == HTTPStatus.NO_CONTENT:
            body = b""
        else:
            text = json.dumps(
                payload,
                default=_encode_json_value,
                allow_nan=False,
                ensure_ascii=True,
            )
            body = text.encode("utf-8")

        self.send_response(status)

        if status != HTTPStatus.NO_CONTENT:
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))

        self.send_header("Connection", "close")

        for name, value in headers.items():
            self.send_header(name, value)

        self.end_headers()

        if body:
            self.wfile.write(body)


def main() -> None:
    """Run the HTTP server until it is stopped."""
    run_identifier = os.environ["METISA_RUN_ID"]
    if not run_identifier:
        raise RuntimeError("Run identifier is required.")

    public_key_path = Path("/sandbox-source/metisa-public-key.pem")
    public_key_pem = public_key_path.read_bytes()
    public_key = serialization.load_pem_public_key(public_key_pem)

    if not isinstance(public_key, rsa.RSAPublicKey):
        raise ValueError("Run verification key must be an RSA public key.")

    _RequestHandler._database_settings = _DatabaseSettings()
    _RequestHandler._run_identifier = run_identifier
    _RequestHandler._public_key = public_key

    with ThreadingHTTPServer(("0.0.0.0", 8000), _RequestHandler) as server:
        server.serve_forever()


def _episode_from_payload(
    payload: dict[str, object],
    namespace: str,
) -> Episode:
    _check_fields(payload, _EPISODE_REQUIRED, _EPISODE_OPTIONAL)

    try:
        episode = Episode(
            id=None,
            namespace=namespace,
            agent_id=cast(str | None, payload.get("agent_id")),
            run_id=cast(str | None, payload.get("run_id")),
            trace_id=cast(str | None, payload.get("trace_id")),
            kind=cast(str, payload["kind"]),
            content=cast(JsonObject, payload["content"]),
            metadata=cast(JsonObject, payload.get("metadata", {})),
            created_at=None,
            expires_at=_parse_datetime(
                payload.get("expires_at"),
                "expires_at",
            ),
        )
        episode.validate()

    except (TypeError, ValueError, RecursionError) as error:
        raise _RequestError(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"Invalid episode: {error}",
        ) from error

    return episode


def _memory_from_payload(
    payload: dict[str, object],
    namespace: str,
    *,
    identifier: UUID | None = None,
) -> Memory:
    _check_fields(payload, _MEMORY_REQUIRED, _MEMORY_OPTIONAL)

    try:
        memory = Memory(
            id=identifier,
            namespace=namespace,
            subject=cast(str, payload["subject"]),
            content=cast(JsonObject, payload["content"]),
            text=cast(str, payload["text"]),
            embedding=cast(list[float], payload["embedding"]),
            metadata=cast(JsonObject, payload.get("metadata", {})),
            valid_to=_parse_datetime(payload.get("valid_to"), "valid_to"),
            created_at=None,
            updated_at=None,
            expires_at=_parse_datetime(
                payload.get("expires_at"),
                "expires_at",
            ),
        )
        memory.validate()

    except (TypeError, ValueError, RecursionError) as error:
        raise _RequestError(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"Invalid memory: {error}",
        ) from error

    return memory


def _check_fields(
    payload: dict[str, object],
    required: frozenset[str],
    optional: frozenset[str],
) -> None:
    supplied = set(payload)

    missing = required - supplied
    if missing:
        names = ", ".join(sorted(missing))
        raise _RequestError(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"Missing fields: {names}.",
        )

    unknown = supplied - required - optional
    if unknown:
        names = ", ".join(sorted(unknown))
        raise _RequestError(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"Unsupported fields: {names}.",
        )


def _parse_datetime(
    value: object,
    name: str,
) -> datetime | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError(f"{name} must be an ISO 8601 string or null.")

    parsed = datetime.fromisoformat(value)

    if parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone.")

    return parsed


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"{value} is not valid JSON.")


def _encode_json_value(value: object) -> str:
    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    raise TypeError(f"Cannot encode {type(value).__name__} as JSON.")


if __name__ == "__main__":
    main()
