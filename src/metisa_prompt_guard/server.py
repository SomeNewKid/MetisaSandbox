"""Server for the Prompt Guard HTTP endpoints."""

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .checker import run_checks
from .koala_moderation import initialize_classifier as initialize_koala_classifier
from .meta_llama import initialize_classifier as initialize_llama_classifier
from .moderator import get_labels

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
        if self.path != "/classify" and self.path != "/moderate":
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
            payload = json.loads(decoded_body)
        except (UnicodeDecodeError, ValueError):
            self.send_error(_CODE_400_BAD_REQUEST, "Expected valid UTF-8 JSON")
            return

        if not isinstance(payload, dict):
            self.send_error(_CODE_400_BAD_REQUEST, "Expected a JSON object")
            return

        text = payload.get("text")
        if not isinstance(text, str):
            self.send_error(_CODE_400_BAD_REQUEST, "'text' must be a string")
            return

        if self.path == "/classify":
            try:
                indicators = run_checks(text)
            except Exception:
                self.send_error(
                    _CODE_500_INTERNAL_SERVER_ERROR, "Classification failed"
                )
                return

            result = {"indicators": [asdict(item) for item in indicators]}
            response_text = json.dumps(result)
        elif self.path == "/moderate":
            try:
                labels = get_labels(text)
            except Exception:
                self.send_error(_CODE_500_INTERNAL_SERVER_ERROR, "Labeling failed")
                return
            result = {"labels": [label for label in labels]}
            response_text = json.dumps(result)
        else:
            self.send_error(_CODE_404_NOT_FOUND)
            return

        body = response_text.encode("utf-8")
        self.send_response(_CODE_200_OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    """Run the HTTP server until it is stopped."""
    initialize_llama_classifier()
    initialize_koala_classifier()

    with ThreadingHTTPServer(("0.0.0.0", 8000), _RequestHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
