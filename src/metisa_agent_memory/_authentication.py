"""Authenticate HTTP requests using host-issued run tokens."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


def get_user_sid(
    request: BaseHTTPRequestHandler,
    public_key: rsa.RSAPublicKey,
    run_identifier: str,
) -> str:
    if not run_identifier:
        raise ValueError("Run identifier is required.")

    authorization_header = request.headers.get("authorization")
    if not authorization_header:
        raise jwt.InvalidTokenError("Expected an Authorization header.")

    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise jwt.InvalidTokenError("Expected a bearer token.")

    token = parts[1]
    if len(token) > 8192:
        raise jwt.InvalidTokenError("Token is too large.")

    claims = jwt.decode(
        jwt=token,
        key=public_key,
        algorithms=["RS256"],
        issuer="metisa-sandbox",
        audience="metisa-agent-memory",
        options={
            "require": ["iss", "sub", "aud", "run", "iat", "exp"],
            "strict_aud": True,
        },
    )

    if claims["run"] != run_identifier:
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
