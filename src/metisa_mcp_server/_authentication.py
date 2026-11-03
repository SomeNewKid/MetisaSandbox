"""Authenticate HTTP requests using host-issued run tokens."""

from __future__ import annotations

from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class RunTokenMiddleware:
    _app: ASGIApp
    _public_key: rsa.RSAPublicKey
    _run_identifier: str

    def __init__(
        self,
        app: ASGIApp,
        *,
        public_key_path: Path,
        run_identifier: str,
    ) -> None:
        if not run_identifier:
            raise ValueError("Run identifier is required.")

        public_key_pem = public_key_path.read_bytes()
        public_key = serialization.load_pem_public_key(public_key_pem)

        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("Run verification key must be an RSA public key.")

        self._app = app
        self._public_key = public_key
        self._run_identifier = run_identifier

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        # Forward startup and shutdown events.
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope)

        # Docker health checks do not carry workload credentials
        if request.method == "GET" and request.url.path == "/health":
            await self._app(scope, receive, send)
            return

        try:
            user_sid = self._authenticate(request)
        except jwt.InvalidTokenError:
            response = JSONResponse(
                {"error": "Request could not be authenticated."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        # Request-local state, avaialble to MCP handlers.
        request.state.user_sid = user_sid
        request.state.run_identifier = self._run_identifier

        await self._app(scope, receive, send)

    def _authenticate(
        self,
        request: Request,
    ) -> str:
        authorization_headers = request.headers.getlist("authorization")
        if len(authorization_headers) != 1:
            raise jwt.InvalidTokenError("Expected one Authorization header.")

        parts = authorization_headers[0].split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise jwt.InvalidTokenError("Expected a bearer token.")

        token = parts[1]
        if len(token) > 8192:
            raise jwt.InvalidTokenError("Token is too large.")

        claims = jwt.decode(
            jwt=token,
            key=self._public_key,
            algorithms=["RS256"],
            issuer="metisa-sandbox",
            audience="metisa-mcp-server",
            options={
                "require": ["iss", "sub", "aud", "run", "iat", "exp"],
                "strict_aud": True,
            },
        )

        if claims["run"] != self._run_identifier:
            raise jwt.InvalidTokenError("Token belongs to another run.")

        user_sid = claims["sub"]
        if not isinstance(user_sid, str) or not user_sid.strip():
            raise jwt.InvalidTokenError("Token subject is invalid.")

        issued_at = claims["iat"]
        expires_at = claims["exp"]  # jwt.decode performs expiry check
        if type(issued_at) is not int or type(expires_at) is not int:
            raise jwt.InvalidTokenError("Token timestamps must be integers.")
        if expires_at <= issued_at:
            raise jwt.InvalidTokenError("Token lifetime is invalid.")

        return user_sid
