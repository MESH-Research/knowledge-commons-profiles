import datetime
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db import models

from knowledge_commons_profiles.cilogon.fields import EncryptedTextField
from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


class SubAssociation(models.Model):
    """
    A model that associates a CI Logon sub with a profile
    """

    sub = models.CharField(
        max_length=255, verbose_name="CI Logon ID", unique=True
    )
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        null=True,
        verbose_name="Associated KC Profile",
    )

    idp_name = models.TextField(verbose_name="IDP Name", blank=True, null=True)

    class Meta:
        verbose_name = "CI Logon Association"
        verbose_name_plural = "CI Logon Associations"

    def __str__(self):
        if self.profile:
            return self.profile.username + " (" + self.sub + ")"
        return f"(no profile) ({self.sub})"


class TokenUserAgentAssociations(models.Model):
    """
    Associates a token with a user agent and an app, allowing
    single-service logout
    """

    user_agent = models.CharField(max_length=255)
    access_token = EncryptedTextField(blank=True, null=True)
    refresh_token = EncryptedTextField(blank=True, null=True)
    app = models.CharField(max_length=255)
    user_name = models.CharField(max_length=255, default="")

    # auto date field updated at time of creation
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user_agent", "user_name", "app"],
                name="tua_ua_user_app_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.app} - [REFRESH] {self.refresh_token} [ACCESS] "
            f"{self.access_token} for {self.user_agent} "
            f"({self.created_at})"
        )


class EmailVerification(models.Model):
    """
    A model that potentially associates a CI Logon sub with a profile
    """

    sub: str = models.CharField(max_length=255)
    secret_uuid: str = models.CharField(
        max_length=255, unique=True, db_index=True
    )
    profile: Profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, null=True
    )
    idp_name = models.TextField(blank=True, null=True)
    created_at: datetime.datetime = models.DateTimeField(
        auto_now_add=True, blank=True, null=True
    )

    def __str__(self):
        return str(self.profile) + " (" + self.sub + ")"

    def is_expired(self) -> bool:
        """
        Check if this verification has expired based on
        VERIFICATION_LIMIT_HOURS.

        Returns:
            bool: True if the verification is older than the configured limit.
        """
        if not self.created_at:
            return True

        expiry_time = self.created_at + datetime.timedelta(
            hours=settings.VERIFICATION_LIMIT_HOURS
        )
        return datetime.datetime.now(tz=datetime.UTC) > expiry_time

    @classmethod
    def garbage_collect(cls):
        """
        Garbage collect this object if it is older than the configured limit
        """
        verifications = EmailVerification.objects.filter(
            created_at__lt=datetime.datetime.now(tz=datetime.UTC)
            - datetime.timedelta(hours=settings.VERIFICATION_LIMIT_HOURS)
        )

        count = verifications.count()

        if count > 0:
            msg = f"Garbage collected {count} email verifications"
            logger.info(msg)

            # delete the verifications
            verifications.delete()


DEFAULT_MAINTENANCE_TITLE = "Login temporarily unavailable"
DEFAULT_MAINTENANCE_MESSAGE = (
    "<p>We are carrying out essential maintenance on the login system. "
    "You will not be able to sign in or edit your profile for a short "
    "while. Please try again later.</p>"
)


class MaintenanceMode(models.Model):
    """
    A single, admin-editable switch that puts the identity system into a
    read-only "maintenance mode".

    When ``enabled`` is set, the silent-SSO broker reports "not logged in" to
    dependent apps (so they degrade gracefully rather than crashing), new
    logins are blocked with the customisable page below, and the site becomes
    read-only.

    There is only ever one row (pinned to ``SINGLETON_PK``). Its state is
    mirrored into the shared cache so both the main app and the standalone
    IDMS broker can read it with a single cache hit, and so a Redis outage
    never takes SSO down (the accessors fail open to "not in maintenance").
    """

    SINGLETON_PK = 1
    CACHE_KEY = "maintenance_mode:state"

    enabled = models.BooleanField(
        default=False,
        help_text=(
            "Turn on to put the identity system into read-only maintenance "
            "mode: logins are blocked and profiles cannot be edited."
        ),
    )
    title = models.CharField(
        max_length=300,
        default=DEFAULT_MAINTENANCE_TITLE,
        help_text="Heading shown on the maintenance page.",
    )
    message = models.TextField(
        default=DEFAULT_MAINTENANCE_MESSAGE,
        help_text="HTML body shown on the maintenance page.",
    )

    class Meta:
        verbose_name = "Maintenance mode"
        verbose_name_plural = "Maintenance mode"

    def __str__(self):
        return f"Maintenance mode ({'ON' if self.enabled else 'off'})"

    def save(self, *args, **kwargs):
        """Pin to the singleton row and write the state through to the cache
        so an admin toggle takes effect on the very next request."""
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)
        cache.set(self.CACHE_KEY, self._as_state(), timeout=None)

    def _as_state(self) -> dict:
        return {
            "enabled": self.enabled,
            "title": self.title,
            "message": self.message,
        }

    @classmethod
    def _default_state(cls) -> dict:
        return {
            "enabled": False,
            "title": DEFAULT_MAINTENANCE_TITLE,
            "message": DEFAULT_MAINTENANCE_MESSAGE,
        }

    @classmethod
    def load(cls) -> "MaintenanceMode":
        """Return the singleton row, creating it with defaults if absent."""
        obj, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return obj

    @classmethod
    def get_state(cls) -> dict:
        """Return ``{"enabled", "title", "message"}`` from cache, falling back
        to the database. Fails open to a disabled state on any error so a cache
        or database outage can never take SSO down with it."""
        try:
            state = cache.get(cls.CACHE_KEY)
            if state is None:
                state = cls.load()._as_state()
                cache.set(cls.CACHE_KEY, state, timeout=None)
        except Exception:
            logger.exception("MaintenanceMode.get_state failed; failing open")
            return cls._default_state()
        else:
            return state

    @classmethod
    async def aget_state(cls) -> dict:
        """Async variant of :meth:`get_state` for the ASGI broker."""
        try:
            state = await cache.aget(cls.CACHE_KEY)
            if state is None:
                obj = await sync_to_async(cls.load)()
                state = obj._as_state()
                await cache.aset(cls.CACHE_KEY, state, timeout=None)
        except Exception:
            logger.exception("MaintenanceMode.aget_state failed; failing open")
            return cls._default_state()
        else:
            return state

    @classmethod
    def is_active(cls) -> bool:
        """Whether maintenance mode is currently on (fails open to False)."""
        return bool(cls.get_state().get("enabled"))

    @classmethod
    async def ais_active(cls) -> bool:
        """Async variant of :meth:`is_active` for the ASGI broker."""
        return bool((await cls.aget_state()).get("enabled"))


class ReservedUsername(models.Model):
    """
    A username term that people may not register during signup.

    Terms are written by staff in plain language. The only special character
    is ``*`` (a wildcard); see ``cilogon.reserved_usernames`` for how a term is
    matched against a candidate username.
    """

    pattern = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Reserved term",
        help_text=(
            "A username term to block. Matching ignores case, hyphens and "
            "underscores, and blocks any username that begins with the term "
            '(so "admin" blocks "admin123"). Use * as a wildcard for any '
            'characters, e.g. "*support*" to block the word anywhere.'
        ),
    )
    note = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional note explaining why this term is reserved.",
    )
    active = models.BooleanField(
        default=True,
        help_text="Untick to disable this term without deleting it.",
    )

    class Meta:
        verbose_name = "Reserved username"
        verbose_name_plural = "Reserved usernames"
        ordering = ["pattern"]

    def __str__(self):
        return self.pattern
