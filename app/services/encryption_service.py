"""Fernet symmetric encryption for at-rest protection of email summaries.

Summaries contain sensitive client data (tax details, financial info) and
must not be stored in plaintext. This module encrypts the JSON summary
before writing to the database and decrypts it on read.

The Fernet key is loaded once from the ENCRYPTION_KEY env var.
Generate a key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import json
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazily initialise the Fernet cipher from the configured key."""
    global _fernet
    if _fernet is None:
        key = settings.encryption_key.encode()
        try:
            _fernet = Fernet(key)
        except (ValueError, Exception) as exc:
            logger.error("Invalid ENCRYPTION_KEY — generate one with Fernet.generate_key()")
            raise ValueError("Invalid encryption key configuration") from exc
    return _fernet


def encrypt(data: dict) -> str:
    """Serialize a dict to JSON and encrypt it. Returns a URL-safe base64 string."""
    plaintext = json.dumps(data).encode("utf-8")
    return _get_fernet().encrypt(plaintext).decode("utf-8")


def decrypt(token: str) -> dict:
    """Decrypt a Fernet token and deserialize the JSON payload.

    Raises:
        InvalidToken: If the key is wrong or the data has been tampered with.
        JSONDecodeError: If the decrypted payload is not valid JSON.
    """
    try:
        plaintext = _get_fernet().decrypt(token.encode("utf-8"))
        return json.loads(plaintext.decode("utf-8"))
    except InvalidToken:
        logger.error("Failed to decrypt summary — key may have been rotated")
        raise
    except json.JSONDecodeError:
        logger.error("Decrypted data is not valid JSON")
        raise
