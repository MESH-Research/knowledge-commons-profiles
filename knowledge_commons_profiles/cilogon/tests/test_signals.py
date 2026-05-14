"""Tests for the auth-user -> session-keys Redis index that lets
`app_logout` fan out to every session a user owns without scanning
the full `django_session` table."""

from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory
from django.test import TestCase

from knowledge_commons_profiles.cilogon.signals import on_user_logged_in
from knowledge_commons_profiles.cilogon.signals import on_user_logged_out
from knowledge_commons_profiles.cilogon.signals import user_session_key


class UserSessionIndexTests(TestCase):
    """Behaviour of the signal handlers as observed at the Redis boundary."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("alice", password="pw")

    def _request_with_session(self, session_key="abc123"):
        request = self.factory.get("/")
        request.session = MagicMock()
        request.session.session_key = session_key
        return request

    def test_user_session_key_is_per_user(self):
        """Different user ids must yield distinct Redis keys."""
        self.assertNotEqual(user_session_key(1), user_session_key(2))

    def test_login_signal_adds_session_to_index(self):
        """user_logged_in must SADD the session_key into the user's set."""
        request = self._request_with_session("session-A")

        fake_redis = MagicMock()
        with patch(
            "knowledge_commons_profiles.cilogon.signals.get_redis_connection",
            return_value=fake_redis,
        ):
            on_user_logged_in(sender=None, request=request, user=self.user)

        fake_redis.sadd.assert_called_once()
        args, _ = fake_redis.sadd.call_args
        self.assertEqual(args[0], user_session_key(self.user.id))
        self.assertEqual(args[1], "session-A")

    def test_login_signal_sets_ttl(self):
        """The set must expire so abandoned indexes don't accumulate."""
        request = self._request_with_session("session-B")
        fake_redis = MagicMock()

        with patch(
            "knowledge_commons_profiles.cilogon.signals.get_redis_connection",
            return_value=fake_redis,
        ):
            on_user_logged_in(sender=None, request=request, user=self.user)

        fake_redis.expire.assert_called_once()
        args, _ = fake_redis.expire.call_args
        self.assertEqual(args[0], user_session_key(self.user.id))
        self.assertGreater(int(args[1]), 0)

    def test_logout_signal_removes_session_from_index(self):
        """user_logged_out must SREM the session_key from the user's set."""
        request = self._request_with_session("session-A")

        fake_redis = MagicMock()
        with patch(
            "knowledge_commons_profiles.cilogon.signals.get_redis_connection",
            return_value=fake_redis,
        ):
            on_user_logged_out(sender=None, request=request, user=self.user)

        fake_redis.srem.assert_called_once()
        args, _ = fake_redis.srem.call_args
        self.assertEqual(args[0], user_session_key(self.user.id))
        self.assertEqual(args[1], "session-A")

    def test_logout_signal_tolerates_anonymous_user(self):
        """Logout fired with no user must not raise."""
        request = self._request_with_session("session-A")
        fake_redis = MagicMock()
        with patch(
            "knowledge_commons_profiles.cilogon.signals.get_redis_connection",
            return_value=fake_redis,
        ):
            on_user_logged_out(sender=None, request=request, user=None)
        fake_redis.srem.assert_not_called()
