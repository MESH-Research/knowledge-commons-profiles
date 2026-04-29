"""
Tests for the import_comanage management command.

These tests focus on COmanage Registry's documented behaviour of returning
HTTP 204 No Content with an empty body when a query has no matching
records (e.g. a CoPerson with no email addresses).  The previous
implementation passed the resulting empty dict straight through to
Pydantic, which raised a ValidationError and aborted the entire import.
"""

from unittest.mock import MagicMock
from unittest.mock import patch

from django.test import SimpleTestCase

from knowledge_commons_profiles.newprofile.management.commands.import_comanage import (  # noqa: E501
    ClientConfig,
)
from knowledge_commons_profiles.newprofile.management.commands.import_comanage import (  # noqa: E501
    COManageClient,
)


def _response(status_code, json_payload=None, text=""):
    """Build a minimal stand-in for a ``requests.Response``."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_payload is None:
        resp.json.side_effect = ValueError("No JSON body")
        resp.text = text
    else:
        resp.json.return_value = json_payload
        resp.text = ""
    return resp


def _co_people_payload(person_id="42"):
    return {
        "ResponseType": "CoPeople",
        "Version": "1.0",
        "CoPeople": [
            {
                "Version": "1.0",
                "Id": person_id,
                "CoId": "2",
                "Status": "A",
                "Created": "2025-01-01T00:00:00Z",
                "Modified": "2025-01-01T00:00:00Z",
                "Revision": "1",
                "Deleted": False,
            }
        ],
    }


def _email_addresses_payload(mail="user@example.test", person_id="42"):
    return {
        "ResponseType": "EmailAddresses",
        "Version": "1.0",
        "EmailAddresses": [
            {
                "Version": "1.0",
                "Id": "1",
                "Mail": mail,
                "Type": "official",
                "Verified": True,
                "Person": {"Type": "CO", "Id": person_id},
                "Created": "2025-01-01T00:00:00Z",
                "Modified": "2025-01-01T00:00:00Z",
            }
        ],
    }


def _co_person_roles_payload(role_id="7", person_id="42", cou_id="11"):
    return {
        "ResponseType": "CoPersonRoles",
        "Version": "1.0",
        "CoPersonRoles": [
            {
                "Version": "1.0",
                "Id": role_id,
                "Person": {"Type": "CO", "Id": person_id},
                "CouId": cou_id,
                "Affiliation": "member",
                "Status": "A",
            }
        ],
    }


def _make_profile(username="alice"):
    profile = MagicMock()
    profile.username = username
    profile.emails = []
    profile.save = MagicMock()
    return profile


class COManageClientGetTests(SimpleTestCase):
    """Direct tests of COManageClient.get() empty-body handling."""

    def _client(self):
        cfg = ClientConfig(
            base_url="https://example.test/",
            username="u",
            password="p",
            verify_ssl=False,
        )
        return COManageClient(cfg)

    def test_get_returns_empty_dict_on_204_no_content(self):
        """A 204 No Content (empty body) returns ``{}`` and does not raise."""
        client = self._client()
        with patch.object(
            client.session, "get", return_value=_response(204)
        ):
            result = client.get("email_addresses.json", params={"x": "1"})
        self.assertEqual(result, {})

    def test_get_returns_empty_dict_on_non_json_200(self):
        """A 200 OK with a non-JSON body still returns ``{}`` (recovery)."""
        client = self._client()
        with patch.object(
            client.session,
            "get",
            return_value=_response(200, text="<html>oops</html>"),
        ):
            result = client.get("email_addresses.json", params={"x": "1"})
        self.assertEqual(result, {})


class IterRolesEmptyResponseTests(SimpleTestCase):
    """``iter_roles`` must tolerate 204 No Content at any endpoint."""

    def _client(self):
        cfg = ClientConfig(
            base_url="https://example.test/",
            username="u",
            password="p",
            verify_ssl=False,
        )
        return COManageClient(cfg)

    def _patch_profiles(self, profiles):
        return patch(
            "knowledge_commons_profiles.newprofile.management.commands."
            "import_comanage.Profile.objects.filter",
            return_value=profiles,
        )

    def _route(self, mapping):
        """Return a side_effect that picks a response per endpoint path.

        ``mapping`` keys are substrings to match against the URL.  Values
        are response objects (not factories — each test owns its own
        ordering by URL).
        """

        def _side_effect(url, **_kwargs):
            for needle, resp in mapping.items():
                if needle in url:
                    return resp
            msg = f"Unexpected URL in test: {url}"
            raise AssertionError(msg)

        return _side_effect

    def test_skips_user_with_no_email_addresses(self):
        """204 on email_addresses.json must not abort the import.

        The role for that user should still be yielded; the user's
        ``emails`` list should be untouched.
        """
        client = self._client()
        profile = _make_profile("alice")

        responses = self._route(
            {
                "co_people.json": _response(200, _co_people_payload()),
                "email_addresses.json": _response(204),
                "co_person_roles.json": _response(
                    200, _co_person_roles_payload()
                ),
            }
        )
        with self._patch_profiles([profile]), patch.object(
            client.session, "get", side_effect=responses
        ):
            yielded = list(client.iter_roles(single_user="alice"))

        self.assertEqual(len(yielded), 1)
        role, _person, _user = yielded[0]
        self.assertEqual(role.Id, "7")
        self.assertEqual(profile.emails, [])

    def test_skips_user_missing_from_comanage(self):
        """204 on co_people.json must skip the user entirely (no yield)."""
        client = self._client()
        profile = _make_profile("ghost")

        responses = self._route(
            {
                "co_people.json": _response(204),
            }
        )
        with self._patch_profiles([profile]), patch.object(
            client.session, "get", side_effect=responses
        ):
            yielded = list(client.iter_roles(single_user="ghost"))

        self.assertEqual(yielded, [])

    def test_skips_user_with_no_roles(self):
        """204 on co_person_roles.json yields nothing but still saves emails."""
        client = self._client()
        profile = _make_profile("bob")

        responses = self._route(
            {
                "co_people.json": _response(200, _co_people_payload()),
                "email_addresses.json": _response(
                    200, _email_addresses_payload(mail="bob@example.test")
                ),
                "co_person_roles.json": _response(204),
            }
        )
        with self._patch_profiles([profile]), patch.object(
            client.session, "get", side_effect=responses
        ):
            yielded = list(client.iter_roles(single_user="bob"))

        self.assertEqual(yielded, [])
        self.assertIn("bob@example.test", profile.emails)

    def test_yields_role_when_all_responses_present(self):
        """Happy path: full responses produce the expected role yield."""
        client = self._client()
        profile = _make_profile("carol")

        responses = self._route(
            {
                "co_people.json": _response(200, _co_people_payload()),
                "email_addresses.json": _response(
                    200, _email_addresses_payload(mail="carol@example.test")
                ),
                "co_person_roles.json": _response(
                    200, _co_person_roles_payload(role_id="99")
                ),
            }
        )
        with self._patch_profiles([profile]), patch.object(
            client.session, "get", side_effect=responses
        ):
            yielded = list(client.iter_roles(single_user="carol"))

        self.assertEqual(len(yielded), 1)
        role, person, user = yielded[0]
        self.assertEqual(role.Id, "99")
        self.assertEqual(person.Id, "42")
        self.assertIs(user, profile)
        self.assertIn("carol@example.test", profile.emails)
