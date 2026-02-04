"""
Tests for the token encryption module.

These tests verify that:
1. Encryption/decryption works correctly
2. Empty values are handled properly
3. Legacy unencrypted tokens are handled gracefully
4. Different keys produce incompatible encryption
5. The EncryptedTextField works correctly with Django models
"""

from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.cilogon.encryption import TokenEncryptor
from knowledge_commons_profiles.cilogon.encryption import (
    get_token_encryption_key,
)
from knowledge_commons_profiles.cilogon.fields import EncryptedTextField
from knowledge_commons_profiles.cilogon.models import (
    TokenUserAgentAssociations,
)


class TokenEncryptorTests(TestCase):
    """Tests for the TokenEncryptor class."""

    def setUp(self):
        self.encryptor = TokenEncryptor()

    def test_encrypt_decrypt_roundtrip(self):
        """Verify encryption and decryption produce the original value."""
        original = "my_secret_access_token_12345"
        encrypted = self.encryptor.encrypt(original)
        decrypted = self.encryptor.decrypt(encrypted)

        self.assertEqual(decrypted, original)
        self.assertNotEqual(encrypted, original)

    def test_encrypted_value_starts_with_prefix(self):
        """Verify encrypted values have the Fernet prefix."""
        encrypted = self.encryptor.encrypt("test_token")

        self.assertTrue(encrypted.startswith(TokenEncryptor.ENCRYPTED_PREFIX))

    def test_is_encrypted_detects_encrypted_values(self):
        """Verify is_encrypted correctly identifies encrypted values."""
        encrypted = self.encryptor.encrypt("test_token")
        plaintext = "plain_token_value"

        self.assertTrue(self.encryptor.is_encrypted(encrypted))
        self.assertFalse(self.encryptor.is_encrypted(plaintext))

    def test_is_encrypted_handles_empty_values(self):
        """Verify is_encrypted handles None and empty strings."""
        self.assertFalse(self.encryptor.is_encrypted(None))
        self.assertFalse(self.encryptor.is_encrypted(""))

    def test_encrypt_none_returns_none(self):
        """Verify encrypting None returns None."""
        result = self.encryptor.encrypt(None)
        self.assertIsNone(result)

    def test_encrypt_empty_string_returns_empty(self):
        """Verify encrypting empty string returns empty string."""
        result = self.encryptor.encrypt("")
        self.assertEqual(result, "")

    def test_decrypt_none_returns_none(self):
        """Verify decrypting None returns None."""
        result = self.encryptor.decrypt(None)
        self.assertIsNone(result)

    def test_decrypt_empty_string_returns_empty(self):
        """Verify decrypting empty string returns empty string."""
        result = self.encryptor.decrypt("")
        self.assertEqual(result, "")

    def test_decrypt_unencrypted_returns_original(self):
        """Verify decrypting plaintext (legacy) token returns it as-is."""
        plaintext = "legacy_unencrypted_token"
        result = self.encryptor.decrypt(plaintext)

        self.assertEqual(result, plaintext)

    def test_each_encryption_produces_unique_ciphertext(self):
        """Verify encrypting the same value twice produces different results."""
        original = "same_token_value"

        encrypted1 = self.encryptor.encrypt(original)
        encrypted2 = self.encryptor.encrypt(original)

        # Different ciphertexts due to random IV
        self.assertNotEqual(encrypted1, encrypted2)

        # But both decrypt to the same value
        self.assertEqual(self.encryptor.decrypt(encrypted1), original)
        self.assertEqual(self.encryptor.decrypt(encrypted2), original)

    def test_long_tokens_handled_correctly(self):
        """Verify long tokens are encrypted and decrypted correctly."""
        # JWT tokens can be quite long
        long_token = "eyJ" + "a" * 1000 + ".eyJ" + "b" * 1000 + ".sig123"

        encrypted = self.encryptor.encrypt(long_token)
        decrypted = self.encryptor.decrypt(encrypted)

        self.assertEqual(decrypted, long_token)

    def test_special_characters_handled(self):
        """Verify tokens with special characters work correctly."""
        special_token = "token+with/special=chars&more"

        encrypted = self.encryptor.encrypt(special_token)
        decrypted = self.encryptor.decrypt(encrypted)

        self.assertEqual(decrypted, special_token)

    def test_unicode_handled(self):
        """Verify Unicode in tokens is handled correctly."""
        unicode_token = "token_with_unicode_\u00e9\u00e8\u00ea"

        encrypted = self.encryptor.encrypt(unicode_token)
        decrypted = self.encryptor.decrypt(encrypted)

        self.assertEqual(decrypted, unicode_token)


class TokenEncryptorKeyTests(TestCase):
    """Tests for encryption key handling."""

    @override_settings(TOKEN_ENCRYPTION_KEY="test_key_123")
    def test_uses_token_encryption_key_when_set(self):
        """Verify TOKEN_ENCRYPTION_KEY is used when available."""
        key = get_token_encryption_key()
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 44)  # Base64-encoded 32 bytes

    @override_settings(
        TOKEN_ENCRYPTION_KEY="", STATIC_API_BEARER="fallback_key"
    )
    def test_raises_when_token_encryption_key_not_set(self):
        """Verify ValueError raised when TOKEN_ENCRYPTION_KEY is not set,
        even if STATIC_API_BEARER is available (no fallback for security)."""
        with self.assertRaises(ValueError) as context:
            get_token_encryption_key()

        self.assertIn(
            "TOKEN_ENCRYPTION_KEY must be set", str(context.exception)
        )

    @override_settings(TOKEN_ENCRYPTION_KEY="", STATIC_API_BEARER="")
    def test_raises_when_no_key_available(self):
        """Verify ValueError raised when no encryption key is available."""
        with self.assertRaises(ValueError) as context:
            get_token_encryption_key()

        self.assertIn(
            "TOKEN_ENCRYPTION_KEY must be set", str(context.exception)
        )

    @override_settings(
        TOKEN_ENCRYPTION_KEY="same_key", STATIC_API_BEARER="same_key"
    )
    def test_warns_when_keys_are_same(self):
        """Verify warning is logged when TOKEN_ENCRYPTION_KEY matches
        STATIC_API_BEARER."""
        with self.assertLogs(
            "knowledge_commons_profiles.cilogon.encryption", level="WARNING"
        ) as log:
            key = get_token_encryption_key()

        self.assertIsNotNone(key)
        self.assertTrue(
            any("SECURITY WARNING" in message for message in log.output)
        )
        self.assertTrue(
            any("should not be the same" in message for message in log.output)
        )

    def test_different_keys_produce_incompatible_encryption(self):
        """Verify tokens encrypted with different keys cannot be decrypted."""
        with override_settings(TOKEN_ENCRYPTION_KEY="key_one"):
            encryptor1 = TokenEncryptor()
            encryptor1._fernet = None  # Reset cached Fernet
            encrypted = encryptor1.encrypt("secret_token")

        with override_settings(TOKEN_ENCRYPTION_KEY="key_two"):
            encryptor2 = TokenEncryptor()
            encryptor2._fernet = None  # Reset cached Fernet

            # Decryption should fail gracefully (return ciphertext as-is)
            # because it looks encrypted but can't be decrypted
            result = encryptor2.decrypt(encrypted)

            # Should return the encrypted value since decryption failed
            # (logged as warning, doesn't raise)
            self.assertEqual(result, encrypted)


class EncryptedTextFieldTests(TestCase):
    """Tests for the EncryptedTextField custom field."""

    def test_get_prep_value_encrypts(self):
        """Verify get_prep_value encrypts plaintext."""
        field = EncryptedTextField()
        plaintext = "my_secret_token"

        result = field.get_prep_value(plaintext)

        self.assertNotEqual(result, plaintext)
        self.assertTrue(result.startswith(TokenEncryptor.ENCRYPTED_PREFIX))

    def test_get_prep_value_none_returns_none(self):
        """Verify get_prep_value returns None for None input."""
        field = EncryptedTextField()

        result = field.get_prep_value(None)

        self.assertIsNone(result)

    def test_get_prep_value_does_not_double_encrypt(self):
        """Verify already-encrypted values are not double-encrypted."""
        field = EncryptedTextField()
        encryptor = TokenEncryptor()

        plaintext = "my_token"
        encrypted = encryptor.encrypt(plaintext)

        result = field.get_prep_value(encrypted)

        # Should return the same encrypted value, not double-encrypt
        self.assertEqual(result, encrypted)

    def test_from_db_value_decrypts(self):
        """Verify from_db_value decrypts encrypted values."""
        field = EncryptedTextField()
        encryptor = TokenEncryptor()

        plaintext = "my_secret_token"
        encrypted = encryptor.encrypt(plaintext)

        result = field.from_db_value(encrypted, None, None)

        self.assertEqual(result, plaintext)

    def test_from_db_value_none_returns_none(self):
        """Verify from_db_value returns None for None input."""
        field = EncryptedTextField()

        result = field.from_db_value(None, None, None)

        self.assertIsNone(result)

    def test_from_db_value_handles_legacy_plaintext(self):
        """Verify from_db_value handles legacy unencrypted values."""
        field = EncryptedTextField()
        legacy_token = "old_plaintext_token"

        result = field.from_db_value(legacy_token, None, None)

        self.assertEqual(result, legacy_token)


class TokenUserAgentAssociationsEncryptionTests(TestCase):
    """Integration tests for encrypted fields in the model."""

    def test_tokens_encrypted_on_save(self):
        """Verify tokens are encrypted when saved to the database."""
        access_token = "test_access_token_12345"
        refresh_token = "test_refresh_token_67890"

        obj = TokenUserAgentAssociations.objects.create(
            user_agent="TestBrowser/1.0",
            access_token=access_token,
            refresh_token=refresh_token,
            app="TestApp",
            user_name="testuser",
        )

        # Fetch raw values from database
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT access_token, refresh_token FROM "
                "cilogon_tokenuseragentassociations WHERE id = %s",
                [obj.id],
            )
            row = cursor.fetchone()

        raw_access, raw_refresh = row

        # Raw values should be encrypted
        self.assertTrue(raw_access.startswith(TokenEncryptor.ENCRYPTED_PREFIX))
        self.assertTrue(
            raw_refresh.startswith(TokenEncryptor.ENCRYPTED_PREFIX)
        )

        # But model values should be decrypted
        obj.refresh_from_db()
        self.assertEqual(obj.access_token, access_token)
        self.assertEqual(obj.refresh_token, refresh_token)

    def test_tokens_decrypted_on_load(self):
        """Verify tokens are decrypted when loaded from the database."""
        access_token = "load_test_access"
        refresh_token = "load_test_refresh"

        obj = TokenUserAgentAssociations.objects.create(
            user_agent="TestBrowser/1.0",
            access_token=access_token,
            refresh_token=refresh_token,
            app="TestApp",
            user_name="testuser",
        )

        # Load fresh from database
        loaded_obj = TokenUserAgentAssociations.objects.get(id=obj.id)

        self.assertEqual(loaded_obj.access_token, access_token)
        self.assertEqual(loaded_obj.refresh_token, refresh_token)

    def test_null_tokens_handled(self):
        """Verify null tokens are handled correctly."""
        obj = TokenUserAgentAssociations.objects.create(
            user_agent="TestBrowser/1.0",
            access_token=None,
            refresh_token=None,
            app="TestApp",
            user_name="testuser",
        )

        obj.refresh_from_db()

        self.assertIsNone(obj.access_token)
        self.assertIsNone(obj.refresh_token)

    def test_update_tokens_re_encrypts(self):
        """Verify updating tokens produces new encrypted values."""
        obj = TokenUserAgentAssociations.objects.create(
            user_agent="TestBrowser/1.0",
            access_token="original_token",
            refresh_token="original_refresh",
            app="TestApp",
            user_name="testuser",
        )

        # Get the original encrypted values
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT access_token FROM "
                "cilogon_tokenuseragentassociations WHERE id = %s",
                [obj.id],
            )
            original_encrypted = cursor.fetchone()[0]

        # Update the token
        obj.access_token = "updated_token"
        obj.save()

        # Get the new encrypted value
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT access_token FROM "
                "cilogon_tokenuseragentassociations WHERE id = %s",
                [obj.id],
            )
            updated_encrypted = cursor.fetchone()[0]

        # Encrypted values should be different
        self.assertNotEqual(original_encrypted, updated_encrypted)

        # Decrypted value should be correct
        obj.refresh_from_db()
        self.assertEqual(obj.access_token, "updated_token")

    def test_filter_by_encrypted_field_not_supported(self):
        """Document that filtering by encrypted field values won't work as
        expected."""
        # This is expected behavior - you can't search encrypted fields
        # by plaintext value. This test documents this limitation.
        TokenUserAgentAssociations.objects.create(
            user_agent="TestBrowser/1.0",
            access_token="searchable_token",
            refresh_token="test_refresh",
            app="TestApp",
            user_name="testuser",
        )

        # Filtering by plaintext value won't find the record
        # because the stored value is encrypted
        result = TokenUserAgentAssociations.objects.filter(
            access_token="searchable_token"
        )

        # This query won't find the record (encrypted values don't match)
        # This is expected behavior - encrypted fields can't be searched
        self.assertEqual(result.count(), 0)
