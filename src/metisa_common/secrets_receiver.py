"""Receive and provision a workload encryption key through stdin."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import InvalidToken

from .secrets_helper import (
    SECRETS_DIRECTORY,
    SECRETS_KEY_FILE,
    decrypt_secrets,
)

_FERNET_KEY_LENGTH = 44


def main() -> int:
    """Validate the supplied key and publish it for bootstrap."""
    try:
        # Read one extra byte so oversized input is rejected.
        encryption_key = sys.stdin.buffer.read(_FERNET_KEY_LENGTH + 1)

        if len(encryption_key) != _FERNET_KEY_LENGTH:
            raise ValueError("Invalid encryption key length.")

        # Validate both the key and the encrypted JSON before publication
        decrypt_secrets(encryption_key)

        _publish_key(encryption_key)

    except (OSError, ValueError, InvalidToken) as error:
        error_type = type(error).__name__
        print(
            f"Secrets provisioning failed: {error_type}.",
            file=sys.stderr,
        )
        return 1

    return 0


def _publish_key(
    encryption_key: bytes,
) -> None:
    file_descriptor, filename = tempfile.mkstemp(
        prefix=".key-",
        dir=SECRETS_DIRECTORY,
    )
    temporary_path = Path(filename)

    try:
        with os.fdopen(file_descriptor, "wb") as file:
            file.write(encryption_key)

        # Publish the complete file atomically, without replacing
        # an already provisioned key. Both paths on same tmpfs.
        os.link(temporary_path, SECRETS_KEY_FILE)

    finally:
        temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
