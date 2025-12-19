"""
Signal handlers for Profile model to handle file deletion from storage.

This module contains Django signals that automatically delete old CV files
from storage when a user uploads a new one or clears the field.
"""

import logging

from django.db.models.signals import post_delete
from django.db.models.signals import pre_save
from django.dispatch import receiver

from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)

# ruff: noqa: BLE001


@receiver(pre_save, sender=Profile)
def delete_old_cv_file_on_update(sender, instance, **kwargs):
    """
    Delete the old CV file from storage when a user uploads a new one
    or clears the field.

    This signal is triggered BEFORE the Profile instance is saved to the
    database.
    It compares the current cv_file with the one in the database and deletes
    the old file if they differ.

    Args:
        sender: The Profile model class
        instance: The Profile instance being saved
        **kwargs: Additional keyword arguments from the signal
    """
    # Check if this is an update (not a new instance)
    if not instance.pk:
        # This is a new Profile, no old file to delete
        return

    try:
        # Get the old Profile instance from the database
        old_instance = Profile.objects.get(pk=instance.pk)
    except Profile.DoesNotExist:
        # Profile doesn't exist in database yet
        return

    # Get the old and new cv_file fields
    old_cv_file = old_instance.cv_file
    new_cv_file = instance.cv_file

    # Check if the cv_file has changed
    if old_cv_file and old_cv_file != new_cv_file:
        # The file has been replaced or cleared
        # Delete the old file from storage
        try:
            old_cv_file.delete(save=False)
            msg = (
                f"Deleted old CV file for user {instance.username}: "
                f"{old_cv_file.name}"
            )
            logger.info(msg)
        except Exception as e:
            msg = (
                f"Error deleting old CV file for user {instance.username}: {e}"
            )
            logger.exception(msg)


@receiver(post_delete, sender=Profile)
def delete_cv_file_on_profile_delete(sender, instance, **kwargs):
    """
    Delete the CV file from storage when a user's Profile is deleted.

    This signal is triggered AFTER the Profile instance is deleted from
    the database. It ensures that orphaned CV files are cleaned up.

    Args:
        sender: The Profile model class
        instance: The Profile instance being deleted
        **kwargs: Additional keyword arguments from the signal
    """
    # Check if the profile has a cv_file
    if instance.cv_file:
        try:
            instance.cv_file.delete(save=False)
            msg = (
                f"Deleted CV file for deleted user {instance.username}: "
                f"{instance.cv_file.name}"
            )
            logger.info(msg)
        except Exception as e:
            msg = f"Error deleting CV file for user {instance.username}: {e}"
            logger.exception(msg)
