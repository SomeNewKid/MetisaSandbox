"""Provides utility methods for working with user identities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import win32api
import win32con
import win32security
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def get_launching_user_sid() -> str:
    """Return the SID of the Windows account launching this process."""
    process_handle = win32api.GetCurrentProcess()
    token_handle = win32security.OpenProcessToken(
        process_handle,
        win32con.TOKEN_QUERY,
    )

    try:
        user_sid, _attributes = win32security.GetTokenInformation(
            token_handle,
            win32security.TokenUser,
        )
        sid_string = win32security.ConvertSidToStringSid(user_sid)
    finally:
        win32api.CloseHandle(token_handle)

    return sid_string


def create_run_signing_key_pair() -> tuple[rsa.RSAPrivateKey, bytes]:
    """Return a fresh private signing key and PEM public key."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    public_key = private_key.public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_key, public_key_pem


def issue_run_token(
    private_key: rsa.RSAPrivateKey,
    *,
    user_sid: str,
    run_identifier: str,
    audience: str,
    lifetime: timedelta,
) -> str:
    """Issue a signed token identifying the user and sandbox run."""
    if not user_sid:
        raise ValueError("User SID is required.")
    if not run_identifier:
        raise ValueError("Run identifier is required.")
    if not audience:
        raise ValueError("Token audience is required.")
    if lifetime < timedelta(seconds=1):
        raise ValueError("Token lifetime must be at least one second")

    issued_at = datetime.now(UTC)
    expires_at = issued_at + lifetime

    claims = {
        "iss": "metisa-sandbox",
        "sub": user_sid,
        "aud": audience,
        "run": run_identifier,
        "iat": issued_at,
        "exp": expires_at,
    }

    token = jwt.encode(
        payload=claims,
        key=private_key,
        algorithm="RS256",
    )

    return token
