"""
Encryption utilities for sensitive data at rest.

This module provides Fernet-based symmetric encryption for storing
sensitive tokens (access_token, refresh_token) in the database.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


def get_token_encryption_key() -> bytes:
    """
    Derive a Fernet-compatible key from the configured secret.

    Requires TOKEN_ENCRYPTION_KEY to be set. This key MUST be different from
    STATIC_API_BEARER to maintain proper key separation between authentication
    and encryption concerns.

    The secret is hashed with SHA256 to produce a consistent 32-byte key,
    which is then base64-encoded for Fernet compatibility.

    Returns:
        bytes: A 32-byte URL-safe base64-encoded key for Fernet.

    Raises:
        ValueError: If TOKEN_ENCRYPTION_KEY is not set or if it matches
        STATIC_API_BEARER.
    """
    secret = getattr(settings, "TOKEN_ENCRYPTION_KEY", None)

    if not secret:
        message = (
            "TOKEN_ENCRYPTION_KEY must be set. This key is used to encrypt "
            "OAuth tokens at rest and must be different from STATIC_API_BEARER."
        )
        raise ValueError(message)

    # Security check: ensure encryption key is different from API bearer token
    api_bearer = getattr(settings, "STATIC_API_BEARER", None)
    if api_bearer and secret == api_bearer:
        logger.warning(
            "SECURITY WARNING: TOKEN_ENCRYPTION_KEY should not be the same as "
            "STATIC_API_BEARER. Using the same secret for authentication and "
            "encryption reduces security - if one is compromised, both are "
            "compromised. Please configure separate secrets."
        )

    # Fernet requires a 32-byte URL-safe base64-encoded key
    # Derive it from the secret using SHA256
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


class TokenEncryptor:
    """
    Encrypt and decrypt tokens using Fernet symmetric encryption.

    Fernet guarantees that a message encrypted using it cannot be
    manipulated or read without the key. It uses AES-128-CBC with
    PKCS7 padding and HMAC-SHA256 for authentication.

    Usage:
        encryptor = TokenEncryptor()
        encrypted = encryptor.encrypt("my_secret_token")
        decrypted = encryptor.decrypt(encrypted)
    """

    # Fernet-encrypted tokens start with this prefix (base64 of version byte)
    ENCRYPTED_PREFIX = "gAAAAA"

    def __init__(self):
        self._fernet = None

    @property
    def fernet(self) -> Fernet:
        """Lazily initialize the Fernet instance."""
        if self._fernet is None:
            self._fernet = Fernet(get_token_encryption_key())
        return self._fernet

    def is_encrypted(self, value: str) -> bool:
        """
        Check if a value appears to be Fernet-encrypted.

        Args:
            value: The string to check.

        Returns:
            bool: True if the value appears to be encrypted.
        """
        if not value:
            return False
        return value.startswith(self.ENCRYPTED_PREFIX)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a token, returning base64-encoded ciphertext.

        Args:
            plaintext: The token to encrypt.

        Returns:
            str: The encrypted token as a base64 string, or the original
                 value if it's None/empty.
        """
        if not plaintext:
            return plaintext
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a token, returning plaintext.

        Handles legacy unencrypted tokens gracefully by returning them
        as-is if decryption fails. This allows for gradual migration
        of existing data.

        Args:
            ciphertext: The encrypted token to decrypt.

        Returns:
            str: The decrypted token, or the original value if it's
                 None/empty or appears to be unencrypted.
        """
        if not ciphertext:
            return ciphertext

        # Check if this looks like an encrypted token
        if not self.is_encrypted(ciphertext):
            # Legacy unencrypted token - return as-is
            # It will be encrypted on next save
            logger.debug("Found unencrypted token, returning as-is")
            return ciphertext

        try:
            return self.fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            # This shouldn't happen for properly encrypted tokens
            # Log a warning and return as-is to avoid data loss
            logger.warning(
                "Failed to decrypt token that appeared encrypted. "
                "This may indicate key mismatch or data corruption."
            )
            return ciphertext


# Module-level singleton for convenience
token_encryptor = TokenEncryptor()
