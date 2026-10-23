"""Provides utility methods for working with secrets."""

from __future__ import annotations

import json
from pathlib import Path

from cryptography.fernet import Fernet


def create_secrets_file(
    target_directory: Path,
    secrets: dict[str, str],
) -> tuple[Path, bytes]:
    """Create the encrypted secrets file in the specified directory."""
    serialized_secrets = json.dumps(secrets)

    encryption_key = Fernet.generate_key()
    cipher = Fernet(encryption_key)

    plaintext = serialized_secrets.encode("utf-8")
    encrypted_secrets = cipher.encrypt(plaintext)

    target_directory.mkdir(parents=True, exist_ok=True)
    secrets_file_path = target_directory / "secrets"

    with open(secrets_file_path, "wb") as f:
        f.write(encrypted_secrets)

    return secrets_file_path, encryption_key
