"""
Migration to encrypt existing tokens in TokenUserAgentAssociations.

This migration:
1. Updates the field type from TextField to EncryptedTextField
2. Encrypts all existing plaintext tokens in the database

The migration is reversible - rolling back will decrypt all tokens.
"""

from django.db import migrations

import knowledge_commons_profiles.cilogon.fields


def encrypt_existing_tokens(apps, schema_editor):
    """
    Encrypt all existing plaintext tokens.

    This function handles the case where tokens may already be encrypted
    (e.g., if the migration is run multiple times or tokens were created
    after the field change but before migration).
    """
    # Import here to avoid issues during migration loading
    from knowledge_commons_profiles.cilogon.encryption import token_encryptor

    TokenUserAgentAssociations = apps.get_model(
        "cilogon", "TokenUserAgentAssociations"
    )

    batch_size = 100
    total_encrypted = 0

    # Process in batches to handle large datasets
    queryset = TokenUserAgentAssociations.objects.all()

    for token_assoc in queryset.iterator(chunk_size=batch_size):
        changed = False

        # Only encrypt if not already encrypted
        if token_assoc.access_token and not token_encryptor.is_encrypted(
            token_assoc.access_token
        ):
            token_assoc.access_token = token_encryptor.encrypt(
                token_assoc.access_token
            )
            changed = True

        if token_assoc.refresh_token and not token_encryptor.is_encrypted(
            token_assoc.refresh_token
        ):
            token_assoc.refresh_token = token_encryptor.encrypt(
                token_assoc.refresh_token
            )
            changed = True

        if changed:
            # Use update_fields to avoid triggering other model logic
            token_assoc.save(update_fields=["access_token", "refresh_token"])
            total_encrypted += 1

    if total_encrypted > 0:
        print(f"\n  Encrypted tokens for {total_encrypted} records")


def decrypt_tokens_for_rollback(apps, schema_editor):
    """
    Decrypt all tokens for migration rollback.

    This allows the migration to be reversed safely.
    """
    from knowledge_commons_profiles.cilogon.encryption import token_encryptor

    TokenUserAgentAssociations = apps.get_model(
        "cilogon", "TokenUserAgentAssociations"
    )

    batch_size = 100
    total_decrypted = 0

    queryset = TokenUserAgentAssociations.objects.all()

    for token_assoc in queryset.iterator(chunk_size=batch_size):
        changed = False

        # Only decrypt if it looks encrypted
        if token_assoc.access_token and token_encryptor.is_encrypted(
            token_assoc.access_token
        ):
            token_assoc.access_token = token_encryptor.decrypt(
                token_assoc.access_token
            )
            changed = True

        if token_assoc.refresh_token and token_encryptor.is_encrypted(
            token_assoc.refresh_token
        ):
            token_assoc.refresh_token = token_encryptor.decrypt(
                token_assoc.refresh_token
            )
            changed = True

        if changed:
            token_assoc.save(update_fields=["access_token", "refresh_token"])
            total_decrypted += 1

    if total_decrypted > 0:
        print(f"\n  Decrypted tokens for {total_decrypted} records")


class Migration(migrations.Migration):
    dependencies = [
        ("cilogon", "0008_subassociation_idp_name"),
    ]

    operations = [
        # Update field types to EncryptedTextField
        # Note: The database column type doesn't change (still TEXT),
        # but Django needs to know about the field class change
        migrations.AlterField(
            model_name="tokenuseragentassociations",
            name="access_token",
            field=knowledge_commons_profiles.cilogon.fields.EncryptedTextField(
                blank=True, null=True
            ),
        ),
        migrations.AlterField(
            model_name="tokenuseragentassociations",
            name="refresh_token",
            field=knowledge_commons_profiles.cilogon.fields.EncryptedTextField(
                blank=True, null=True
            ),
        ),
        # Encrypt existing data
        migrations.RunPython(
            encrypt_existing_tokens,
            reverse_code=decrypt_tokens_for_rollback,
        ),
    ]
