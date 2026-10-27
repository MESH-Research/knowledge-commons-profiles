import os
from unittest.mock import Mock
from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from knowledge_commons_profiles.newprofile import ecs_metadata

METADATA_URI = "http://169.254.170.2/v4/abc123"


def metadata_response(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TestEcsServiceName(SimpleTestCase):
    def setUp(self):
        ecs_metadata.ecs_service_name.cache_clear()

    def tearDown(self):
        ecs_metadata.ecs_service_name.cache_clear()

    def test_returns_none_when_not_on_ecs(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(ecs_metadata.ecs_service_name())

    def test_environment_override_wins(self):
        env = {
            "ECS_SERVICE_NAME": "kcprofiles-blue",
            "ECS_CONTAINER_METADATA_URI_V4": METADATA_URI,
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(ecs_metadata.requests, "get") as mock_get,
        ):
            result = ecs_metadata.ecs_service_name()

        self.assertEqual(result, "kcprofiles-blue")
        mock_get.assert_not_called()

    def test_reads_service_name_from_task_metadata(self):
        env = {"ECS_CONTAINER_METADATA_URI_V4": METADATA_URI}
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(
                ecs_metadata.requests,
                "get",
                return_value=metadata_response(
                    {"Cluster": "kcprofiles", "ServiceName": "kcprofiles-blue"}
                ),
            ) as mock_get,
        ):
            result = ecs_metadata.ecs_service_name()

        self.assertEqual(result, "kcprofiles-blue")
        requested_url = mock_get.call_args.args[0]
        self.assertEqual(requested_url, f"{METADATA_URI}/task")

    def test_returns_none_when_metadata_lacks_service_name(self):
        env = {"ECS_CONTAINER_METADATA_URI_V4": METADATA_URI}
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(
                ecs_metadata.requests,
                "get",
                return_value=metadata_response({"Cluster": "kcprofiles"}),
            ),
        ):
            self.assertIsNone(ecs_metadata.ecs_service_name())

    def test_returns_none_when_metadata_endpoint_fails(self):
        env = {"ECS_CONTAINER_METADATA_URI_V4": METADATA_URI}
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(
                ecs_metadata.requests,
                "get",
                side_effect=requests.exceptions.ConnectionError("down"),
            ),
        ):
            self.assertIsNone(ecs_metadata.ecs_service_name())

    def test_returns_none_when_metadata_is_not_json(self):
        bad = Mock()
        bad.raise_for_status.return_value = None
        bad.json.side_effect = ValueError("not json")
        env = {"ECS_CONTAINER_METADATA_URI_V4": METADATA_URI}
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(ecs_metadata.requests, "get", return_value=bad),
        ):
            self.assertIsNone(ecs_metadata.ecs_service_name())

    def test_metadata_request_uses_a_short_timeout(self):
        env = {"ECS_CONTAINER_METADATA_URI_V4": METADATA_URI}
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(
                ecs_metadata.requests,
                "get",
                return_value=metadata_response({"ServiceName": "x"}),
            ) as mock_get,
        ):
            ecs_metadata.ecs_service_name()

        timeout = mock_get.call_args.kwargs.get("timeout")
        self.assertIsNotNone(timeout)
        self.assertLessEqual(timeout, 5)

    def test_result_is_cached_until_cleared(self):
        with patch.dict(os.environ, {"ECS_SERVICE_NAME": "first"}, clear=True):
            self.assertEqual(ecs_metadata.ecs_service_name(), "first")
        with patch.dict(os.environ, {"ECS_SERVICE_NAME": "second"}, clear=True):
            self.assertEqual(ecs_metadata.ecs_service_name(), "first")
            ecs_metadata.ecs_service_name.cache_clear()
            self.assertEqual(ecs_metadata.ecs_service_name(), "second")
