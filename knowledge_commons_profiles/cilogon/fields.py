"""
Custom encrypted model fields for sensitive data storage.

These fields provide transparent encryption/decryption of data at rest,
ensuring that sensitive tokens are never stored in plaintext in the database.
"""

from django.db import models

from knowledge_commons_profiles.cilogon.encryption import token_encryptor


class EncryptedTextField(models.TextField):
    """
    A TextField that encrypts data at rest using Fernet encryption.

    Data is automatically encrypted before saving to the database and
    decrypted when loading. This is transparent to application code -
    it interacts with plaintext values, and encryption happens behind
    the scenes.

    The field handles legacy unencrypted data gracefully, allowing for
    gradual migration of existing records.

    Example:
        class MyModel(models.Model):
            secret_token = EncryptedTextField(blank=True, null=True)

        # Usage is identical to TextField:
        obj = MyModel.objects.create(secret_token="my_secret")
        obj.refresh_from_db()
        assert obj.secret_token == "my_secret"  # Decrypted automatically
    """

    description = "An encrypted TextField for sensitive data"

    def get_prep_value(self, value):
        """
        Encrypt the value before saving to the database.

        Args:
            value: The plaintext value to encrypt.

        Returns:
            The encrypted value, or None if value is None.
        """
        if value is None:
            return value

        # Don't double-encrypt already encrypted values
        if token_encryptor.is_encrypted(value):
            return value

        return token_encryptor.encrypt(value)

    def from_db_value(self, value, expression, connection):
        """
        Decrypt the value when loading from the database.

        Args:
            value: The encrypted value from the database.
            expression: The SQL expression (unused).
            connection: The database connection (unused).

        Returns:
            The decrypted value, or None if value is None.
        """
        if value is None:
            return value
        return token_encryptor.decrypt(value)

    def to_python(self, value):
        """
        Convert the value to a Python string.

        This is called during form validation and deserialization.
        Since from_db_value already handles decryption, we just
        need to handle the case where value is already a string.

        Args:
            value: The value to convert.

        Returns:
            The value as a string, or None if value is None.
        """
        if value is None:
            return value
        return str(value)
