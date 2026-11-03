"""Server for the Prompt Guard HTTP endpoints."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from ._authentication import get_user_sid

_MAX_REQUEST_BYTES = 1024 * 1024  # 1 MiB
_CODE_200_OK = 200
_CODE_400_BAD_REQUEST = 400
_CODE_404_NOT_FOUND = 404
_CODE_411_LENGTH_REQUIRED = 411
_CODE_413_CONTENT_TOO_LARGE_413 = 413
_CODE_415_UNSUPPORTED_MEDIA_TYPE = 415
_CODE_500_INTERNAL_SERVER_ERROR = 500


class _RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(_CODE_404_NOT_FOUND)
            return

        body = b"Healthy"
        self.send_response(_CODE_200_OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        run_identifier = os.environ["METISA_RUN_ID"]
        if not run_identifier:
            raise ValueError("Run identifier not available.")

        public_key_path = Path("/sandbox-source/metisa-public-key.pem")
        public_key_pem = public_key_path.read_bytes()
        public_key = serialization.load_pem_public_key(public_key_pem)

        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("Run verification key must be an RSA public key.")

        user_sid = get_user_sid(self, public_key, run_identifier)
        if not user_sid:
            raise RuntimeError("Memory access requires user SID.")

        if self.path != "/hello":
            self.send_error(_CODE_404_NOT_FOUND)
            return

        if self.headers.get_content_type() != "application/json":
            self.send_error(
                _CODE_415_UNSUPPORTED_MEDIA_TYPE, "Expected application/json"
            )
            return

        if self.headers.get("Transfer-Encoding") is not None:
            self.send_error(_CODE_400_BAD_REQUEST, "Transfer-Encoding is not supported")
            return

        length_header = self.headers.get("Content-Length")
        if length_header is None:
            self.send_error(_CODE_411_LENGTH_REQUIRED, "Content-Length is required")
            return

        try:
            length = int(length_header)
        except ValueError:
            self.send_error(_CODE_400_BAD_REQUEST, "Invalid Content-Length")
            return

        if length < 0:
            self.send_error(_CODE_400_BAD_REQUEST, "Invalid Content-Length")
            return

        if length > _MAX_REQUEST_BYTES:
            self.send_error(
                _CODE_413_CONTENT_TOO_LARGE_413, "Request body is too large"
            )
            return

        raw_body = self.rfile.read(length)
        try:
            decoded_body = raw_body.decode("utf-8")
            request_payload = json.loads(decoded_body)
        except (UnicodeDecodeError, ValueError):
            self.send_error(_CODE_400_BAD_REQUEST, "Expected valid UTF-8 JSON")
            return

        if not isinstance(request_payload, dict):
            self.send_error(_CODE_400_BAD_REQUEST, "Expected a JSON object")
            return

        text = request_payload.get("text")
        if not isinstance(text, str):
            self.send_error(_CODE_400_BAD_REQUEST, "'text' must be a string")
            return

        if self.path == "/hello":
            try:
                result = {"message": "Hello, World!"}
            except Exception:
                self.send_error(_CODE_500_INTERNAL_SERVER_ERROR, "Labeling failed")
                return
            response_payload = json.dumps(result)
        else:
            self.send_error(_CODE_404_NOT_FOUND)
            return

        body = response_payload.encode("utf-8")
        self.send_response(_CODE_200_OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    """Run the HTTP server until it is stopped."""
    with ThreadingHTTPServer(("0.0.0.0", 8000), _RequestHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
