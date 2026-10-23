"""Provides utility functions for working with secrets."""

from __future__ import annotations

import json
import time
from pathlib import Path

from cryptography.fernet import Fernet

SECRETS_DIRECTORY = Path("/run/metisa-secrets")
SECRETS_KEY_FILE = SECRETS_DIRECTORY / "key"
ENCRYPTED_SECRETS_FILE = Path("/sandbox-source/secrets")


def decrypt_secrets(
    encryption_key: bytes,
) -> dict[str, str]:
    """Decrypt and validate the secret declarations."""
    cipher = Fernet(encryption_key)
    ciphertext = ENCRYPTED_SECRETS_FILE.read_bytes()
    plaintext = cipher.decrypt(ciphertext)

    secrets = json.loads(plaintext)

    if not isinstance(secrets, dict):
        raise ValueError("Secrets must be a JSON object.")

    for name, value in secrets.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("Secret names and values must be strings.")

    return secrets


def load_secrets() -> dict[str, str]:
    """Read the provisioned key and decrypt the secrets file."""
    encryption_key = SECRETS_KEY_FILE.read_bytes()
    return decrypt_secrets(encryption_key)


def wait_for_secrets(
    timeout_seconds: float = 30.0,
) -> None:
    """Wait for the secrets provisioning to complete."""
    if timeout_seconds < 0:
        raise ValueError("Timeout must be greater than zero.")

    deadline = time.monotonic() + timeout_seconds

    while True:
        if SECRETS_KEY_FILE.is_file():
            return

        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            raise TimeoutError("Secrets provisioning did not complete.")

        time.sleep(min(0.1, remaining_seconds))
