"""
Test suite for website uptime monitor module.
"""

import json
import subprocess
from datetime import UTC
from datetime import datetime
from unittest import mock

import pytest
import requests

from knowledge_commons_profiles.cron import monitor_website
from knowledge_commons_profiles.cron.monitor_website import HTTP_STATUS_OK_MAX
from knowledge_commons_profiles.cron.monitor_website import HTTP_STATUS_OK_MIN
from knowledge_commons_profiles.cron.monitor_website import MonitorPhase
from knowledge_commons_profiles.cron.monitor_website import MonitorState
from knowledge_commons_profiles.cron.monitor_website import _now
from knowledge_commons_profiles.cron.monitor_website import build_cmd
from knowledge_commons_profiles.cron.monitor_website import (
    check_activation_timeout,
)
from knowledge_commons_profiles.cron.monitor_website import check_grace_period
from knowledge_commons_profiles.cron.monitor_website import check_website_status
from knowledge_commons_profiles.cron.monitor_website import delete_state_from_s3
from knowledge_commons_profiles.cron.monitor_website import (
    get_listener_rule_details,
)
from knowledge_commons_profiles.cron.monitor_website import handle_site_down
from knowledge_commons_profiles.cron.monitor_website import handle_site_up
from knowledge_commons_profiles.cron.monitor_website import (
    initialize_state_from_s3,
)
from knowledge_commons_profiles.cron.monitor_website import load_state_from_s3
from knowledge_commons_profiles.cron.monitor_website import (
    normalize_condition_format,
)
from knowledge_commons_profiles.cron.monitor_website import (
    remove_http_method_restriction,
)
from knowledge_commons_profiles.cron.monitor_website import (
    restore_http_method_restriction,
)
from knowledge_commons_profiles.cron.monitor_website import save_state_to_s3
from knowledge_commons_profiles.cron.monitor_website import (
    send_deactivation_email,
)
from knowledge_commons_profiles.cron.monitor_website import send_email
from knowledge_commons_profiles.cron.monitor_website import state

# Test constants
TEST_FAILURE_COUNT = 5
EXPECTED_STATUS_OK_MIN = 200
EXPECTED_STATUS_OK_MAX = 400
TEST_RULE_ARN = (
    "arn:aws:elasticloadbalancing:us-east-1:123456789:listener-rule/test"
)
TEST_S3_BUCKET = "test-bucket"
TEST_S3_KEY = "monitor/alb-rule-state.json"


class TestMonitorState:
    """Tests for the MonitorState dataclass."""

    def test_default_values(self):
        """Test that MonitorState has correct default values."""
        monitor_state = MonitorState()
        assert monitor_state.consecutive_failures == 0
        assert monitor_state.phase == MonitorPhase.MONITORING
        assert monitor_state.activated_at is None
        assert monitor_state.original_http_methods is None
        assert monitor_state.grace_period_start is None
        assert monitor_state.test_mode is False

    def test_custom_values(self):
        """Test that MonitorState accepts custom values."""
        now = datetime(2026, 3, 30, 12, 0, 0, tzinfo=UTC)
        monitor_state = MonitorState(
            consecutive_failures=TEST_FAILURE_COUNT,
            phase=MonitorPhase.ACTIVATED,
            activated_at=now,
            original_http_methods=["GET", "POST"],
            grace_period_start=None,
            test_mode=True,
        )
        assert monitor_state.consecutive_failures == TEST_FAILURE_COUNT
        assert monitor_state.phase == MonitorPhase.ACTIVATED
        assert monitor_state.activated_at == now
        assert monitor_state.original_http_methods == ["GET", "POST"]
        assert monitor_state.test_mode is True


class TestCheckWebsiteStatus:
    """Tests for the check_website_status function."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset the global state before each test."""
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False
        yield
        # Reset after test too
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False

    def test_returns_true_for_successful_response(self):
        """Test that check_website_status returns True for 2xx responses."""
        with mock.patch("requests.get") as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = check_website_status("https://example.com")

            assert result is True
            mock_get.assert_called_once_with(
                "https://example.com",
                timeout=10,
                allow_redirects=True,
            )

    def test_returns_true_for_redirect_response(self):
        """Test that check_website_status returns True for 3xx responses."""
        with mock.patch("requests.get") as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 301
            mock_get.return_value = mock_response

            result = check_website_status("https://example.com")

            assert result is True

    def test_returns_false_for_client_error(self):
        """Test that check_website_status returns False for 4xx responses."""
        with mock.patch("requests.get") as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = check_website_status("https://example.com")

            assert result is False

    def test_returns_false_for_server_error(self):
        """Test that check_website_status returns False for 5xx responses."""
        with mock.patch("requests.get") as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            result = check_website_status("https://example.com")

            assert result is False

    def test_returns_false_on_timeout(self):
        """Test that check_website_status returns False on timeout."""
        with mock.patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()

            result = check_website_status("https://example.com")

            assert result is False

    def test_returns_false_on_connection_error(self):
        """Test that check_website_status returns False on connection error."""
        with mock.patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()

            result = check_website_status("https://example.com")

            assert result is False

    def test_returns_false_on_request_exception(self):
        """Test that check_website_status returns False on generic exception."""
        with mock.patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException()

            result = check_website_status("https://example.com")

            assert result is False

    def test_returns_false_in_test_mode(self):
        """Test that check_website_status returns False when test mode is on."""
        state.test_mode = True

        with mock.patch("requests.get") as mock_get:
            result = check_website_status("https://example.com")

            assert result is False
            # Should not make any HTTP requests in test mode
            mock_get.assert_not_called()

    def test_status_boundaries(self):
        """Test the status code boundaries are correct."""
        assert HTTP_STATUS_OK_MIN == EXPECTED_STATUS_OK_MIN
        assert HTTP_STATUS_OK_MAX == EXPECTED_STATUS_OK_MAX

        with mock.patch("requests.get") as mock_get:
            # Test lower boundary (200 - should be OK)
            mock_response = mock.Mock()
            mock_response.status_code = EXPECTED_STATUS_OK_MIN
            mock_get.return_value = mock_response
            assert check_website_status("https://example.com") is True

            # Test upper boundary exclusive (400 - should NOT be OK)
            mock_response.status_code = EXPECTED_STATUS_OK_MAX
            assert check_website_status("https://example.com") is False

            # Test just below upper boundary (399 - should be OK)
            mock_response.status_code = EXPECTED_STATUS_OK_MAX - 1
            assert check_website_status("https://example.com") is True


class TestNormalizeConditionFormat:
    """Tests for the normalize_condition_format function."""

    def test_with_existing_config_key(self):
        """Test normalization when condition already has a Config key."""
        condition = {
            "Field": "path-pattern",
            "PathPatternConfig": {"Values": ["/api/*"]},
            "Values": ["/api/*"],  # Old format should be stripped
        }

        result = normalize_condition_format(condition)

        assert result == {
            "Field": "path-pattern",
            "PathPatternConfig": {"Values": ["/api/*"]},
        }
        assert "Values" not in result

    def test_converts_path_pattern_values(self):
        """Test conversion of path-pattern Values to Config format."""
        condition = {
            "Field": "path-pattern",
            "Values": ["/members/*", "/profile/*"],
        }

        result = normalize_condition_format(condition)

        assert result == {
            "Field": "path-pattern",
            "PathPatternConfig": {"Values": ["/members/*", "/profile/*"]},
        }

    def test_converts_host_header_values(self):
        """Test conversion of host-header Values to Config format."""
        condition = {
            "Field": "host-header",
            "Values": ["example.com", "www.example.com"],
        }

        result = normalize_condition_format(condition)

        assert result == {
            "Field": "host-header",
            "HostHeaderConfig": {
                "Values": ["example.com", "www.example.com"],
            },
        }

    def test_converts_http_request_method_values(self):
        """Test conversion of http-request-method Values to Config format."""
        condition = {
            "Field": "http-request-method",
            "Values": ["GET", "POST"],
        }

        result = normalize_condition_format(condition)

        assert result == {
            "Field": "http-request-method",
            "HttpRequestMethodConfig": {"Values": ["GET", "POST"]},
        }

    def test_converts_source_ip_values(self):
        """Test conversion of source-ip Values to Config format."""
        condition = {
            "Field": "source-ip",
            "Values": ["192.168.1.0/24"],
        }

        result = normalize_condition_format(condition)

        assert result == {
            "Field": "source-ip",
            "SourceIpConfig": {"Values": ["192.168.1.0/24"]},
        }

    def test_converts_query_string_values(self):
        """Test conversion of query-string Values to Config format."""
        condition = {
            "Field": "query-string",
            "Values": ["key=value"],
        }

        result = normalize_condition_format(condition)

        assert result == {
            "Field": "query-string",
            "QueryStringConfig": {"Values": ["key=value"]},
        }

    def test_returns_unknown_field_as_is(self):
        """Test that unknown fields are returned unchanged."""
        condition = {
            "Field": "unknown-field",
            "Values": ["some-value"],
            "SomeOtherKey": "data",
        }

        result = normalize_condition_format(condition)

        assert result == condition


class TestBuildCmd:
    """Tests for the build_cmd function."""

    def test_builds_correct_command(self):
        """Test that build_cmd creates the correct AWS CLI command."""
        conditions = [
            {
                "Field": "path-pattern",
                "PathPatternConfig": {"Values": ["/*"]},
            }
        ]

        result = build_cmd(conditions, TEST_RULE_ARN)

        assert result == [
            "aws",
            "elbv2",
            "modify-rule",
            "--rule-arn",
            TEST_RULE_ARN,
            "--conditions",
            json.dumps(conditions),
        ]

    def test_handles_empty_conditions(self):
        """Test that build_cmd handles empty conditions list."""
        conditions = []
        rule_arn = "arn:aws:test"

        result = build_cmd(conditions, rule_arn)

        assert "--conditions" in result
        assert "[]" in result


class TestGetListenerRuleDetails:
    """Tests for the get_listener_rule_details function."""

    def test_returns_rule_on_success(self):
        """Test successful retrieval of listener rule details."""
        mock_output = {
            "Rules": [
                {
                    "RuleArn": "test-arn",
                    "Conditions": [
                        {"Field": "path-pattern", "Values": ["/*"]},
                    ],
                }
            ]
        }

        with mock.patch("subprocess.run") as mock_run:
            mock_result = mock.Mock()
            mock_result.stdout = json.dumps(mock_output)
            mock_run.return_value = mock_result

            result = get_listener_rule_details("test-arn")

            assert result == mock_output["Rules"][0]
            mock_run.assert_called_once()

    def test_returns_none_on_empty_rules(self):
        """Test that None is returned when no rules are found."""
        mock_output = {"Rules": []}

        with mock.patch("subprocess.run") as mock_run:
            mock_result = mock.Mock()
            mock_result.stdout = json.dumps(mock_output)
            mock_run.return_value = mock_result

            result = get_listener_rule_details("test-arn")

            assert result is None

    def test_returns_none_on_subprocess_error(self):
        """Test that None is returned on subprocess error."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "aws", stderr="Error"
            )

            result = get_listener_rule_details("test-arn")

            assert result is None

    def test_returns_none_on_json_decode_error(self):
        """Test that None is returned when JSON parsing fails."""
        with mock.patch("subprocess.run") as mock_run:
            mock_result = mock.Mock()
            mock_result.stdout = "invalid json"
            mock_run.return_value = mock_result

            result = get_listener_rule_details("test-arn")

            assert result is None


class TestRemoveHttpMethodRestriction:
    """Tests for the remove_http_method_restriction function."""

    def test_returns_true_on_success(self):
        """Test successful removal of HTTP method restriction."""
        mock_rule = {
            "Conditions": [
                {"Field": "path-pattern", "Values": ["/*"]},
                {"Field": "http-request-method", "Values": ["GET", "POST"]},
            ]
        }

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "get_listener_rule_details"
            ) as mock_get,
            mock.patch("subprocess.run") as mock_run,
        ):
            mock_get.return_value = mock_rule
            mock_result = mock.Mock()
            mock_result.stdout = "{}"
            mock_run.return_value = mock_result

            result = remove_http_method_restriction("test-arn")

            assert result is True

    def test_returns_false_when_no_rule_found(self):
        """Test that False is returned when rule cannot be retrieved."""
        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website."
            "get_listener_rule_details"
        ) as mock_get:
            mock_get.return_value = None

            result = remove_http_method_restriction("test-arn")

            assert result is False

    def test_returns_false_when_no_http_method_condition(self):
        """Test False is returned when no HTTP method restriction exists."""
        mock_rule = {
            "Conditions": [
                {"Field": "path-pattern", "Values": ["/*"]},
            ]
        }

        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website."
            "get_listener_rule_details"
        ) as mock_get:
            mock_get.return_value = mock_rule

            result = remove_http_method_restriction("test-arn")

            assert result is False

    def test_returns_false_on_subprocess_error(self):
        """Test that False is returned when AWS CLI command fails."""
        mock_rule = {
            "Conditions": [
                {"Field": "http-request-method", "Values": ["GET"]},
            ]
        }

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "get_listener_rule_details"
            ) as mock_get,
            mock.patch("subprocess.run") as mock_run,
        ):
            mock_get.return_value = mock_rule
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "aws", stderr="Error"
            )

            result = remove_http_method_restriction("test-arn")

            assert result is False


class TestSendEmail:
    """Tests for the send_email function."""

    def test_sends_email_with_correct_parameters(self):
        """Test that send_email sends with correct parameters."""
        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website.SparkPostEmailClient"
        ) as mock_client_class:
            mock_client = mock.Mock()
            mock_client.send_email.return_value = {"success": True}
            mock_client_class.return_value = mock_client

            result = send_email()

            mock_client.send_email.assert_called_once()
            call_kwargs = mock_client.send_email.call_args[1]

            assert call_kwargs["from_email"] == "system@hcommons.org"
            assert call_kwargs["from_name"] == "Knowledge Commons System"
            expected_subject = "DDOS Protection has been activated"
            assert call_kwargs["subject"] == expected_subject
            assert "Attack Blocked" in call_kwargs["html_content"]
            assert "Attack Blocked" in call_kwargs["text_content"]
            assert call_kwargs["tags"] == ["system", "ddos"]
            assert result == {"success": True}


class TestHandleSiteUp:
    """Tests for the handle_site_up function."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset the global state before each test."""
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False
        yield
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False

    def test_resets_consecutive_failures(self):
        """Test that handle_site_up resets the failure counter."""
        state.consecutive_failures = TEST_FAILURE_COUNT

        handle_site_up()

        assert state.consecutive_failures == 0

    def test_does_not_change_phase(self):
        """Test that phase is not changed by handle_site_up."""
        handle_site_up()

        assert state.phase == MonitorPhase.MONITORING


class TestHandleSiteDown:
    """Tests for the handle_site_down function."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset the global state before each test."""
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False
        yield
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False

    def test_increments_consecutive_failures(self):
        """Test that handle_site_down increments the failure counter."""
        state.consecutive_failures = 0

        handle_site_down()

        assert state.consecutive_failures == 1

    def test_does_not_modify_rule_below_threshold(self):
        """Test that rule is not modified below the threshold."""
        state.consecutive_failures = 0

        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website."
            "remove_http_method_restriction"
        ) as mock_remove:
            handle_site_down()

            mock_remove.assert_not_called()

    def test_modifies_rule_at_threshold(self):
        """Test that rule is modified when threshold is reached."""
        state.consecutive_failures = monitor_website.SITE_DOWN_THRESHOLD - 1
        now = datetime(2026, 3, 30, 12, 0, 0, tzinfo=UTC)

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "get_listener_rule_details"
            ) as mock_get,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "remove_http_method_restriction"
            ) as mock_remove,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website.send_email"
            ) as mock_email,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "save_state_to_s3"
            ) as mock_save,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website._now"
            ) as mock_now,
        ):
            mock_get.return_value = {
                "Conditions": [
                    {
                        "Field": "http-request-method",
                        "HttpRequestMethodConfig": {
                            "Values": ["GET", "POST"],
                        },
                    },
                ]
            }
            mock_remove.return_value = True
            mock_now.return_value = now

            handle_site_down()

            mock_remove.assert_called_once()
            mock_email.assert_called_once()
            mock_save.assert_called_once()
            assert state.phase == MonitorPhase.ACTIVATED
            assert state.activated_at == now
            assert state.original_http_methods == ["GET", "POST"]

    def test_captures_original_http_methods_from_rule(self):
        """Test that original HTTP methods are extracted from the rule."""
        state.consecutive_failures = monitor_website.SITE_DOWN_THRESHOLD - 1

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "get_listener_rule_details"
            ) as mock_get,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "remove_http_method_restriction"
            ) as mock_remove,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website.send_email"
            ),
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "save_state_to_s3"
            ),
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website._now"
            ) as mock_now,
        ):
            mock_get.return_value = {
                "Conditions": [
                    {
                        "Field": "http-request-method",
                        "HttpRequestMethodConfig": {
                            "Values": ["GET"],
                        },
                    },
                ]
            }
            mock_remove.return_value = True
            mock_now.return_value = datetime(
                2026, 3, 30, 12, 0, 0, tzinfo=UTC
            )

            handle_site_down()

            assert state.original_http_methods == ["GET"]

    def test_does_not_modify_rule_if_already_activated(self):
        """Test that rule is not modified when already activated."""
        state.consecutive_failures = monitor_website.SITE_DOWN_THRESHOLD
        state.phase = MonitorPhase.ACTIVATED

        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website."
            "remove_http_method_restriction"
        ) as mock_remove:
            handle_site_down()

            mock_remove.assert_not_called()

    def test_handles_modification_failure(self):
        """Test handling when rule modification fails."""
        state.consecutive_failures = monitor_website.SITE_DOWN_THRESHOLD - 1

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "get_listener_rule_details"
            ) as mock_get,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "remove_http_method_restriction"
            ) as mock_remove,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website.send_email"
            ) as mock_email,
        ):
            mock_get.return_value = {"Conditions": []}
            mock_remove.return_value = False

            handle_site_down()

            mock_email.assert_not_called()
            assert state.phase == MonitorPhase.MONITORING


class TestNow:
    """Tests for the _now helper function."""

    def test_returns_utc_datetime(self):
        """Test that _now returns a timezone-aware UTC datetime."""
        result = _now()
        assert result.tzinfo == UTC


class TestSaveStateToS3:
    """Tests for the save_state_to_s3 function."""

    def test_saves_correct_json_via_aws_cli(self):
        """Test that correct JSON is piped to aws s3 cp."""
        now = datetime(2026, 3, 30, 14, 22, 0, tzinfo=UTC)
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0)

            result = save_state_to_s3(
                TEST_S3_BUCKET,
                TEST_S3_KEY,
                now,
                ["GET", "POST"],
                TEST_RULE_ARN,
            )

            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            # Verify the JSON input contains correct data
            input_json = json.loads(call_args.kwargs.get("input", ""))
            assert input_json["activated_at"] == now.isoformat()
            assert input_json["original_http_methods"] == ["GET", "POST"]
            assert input_json["rule_arn"] == TEST_RULE_ARN
            assert input_json["version"] == 1

    def test_returns_false_on_subprocess_error(self):
        """Test that False is returned on subprocess error."""
        now = datetime(2026, 3, 30, 14, 22, 0, tzinfo=UTC)
        with mock.patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "aws", stderr="Error"
            )

            result = save_state_to_s3(
                TEST_S3_BUCKET,
                TEST_S3_KEY,
                now,
                ["GET", "POST"],
                TEST_RULE_ARN,
            )

            assert result is False

    def test_returns_false_when_no_bucket_configured(self):
        """Test that False is returned when bucket is empty."""
        now = datetime(2026, 3, 30, 14, 22, 0, tzinfo=UTC)
        result = save_state_to_s3(
            "", TEST_S3_KEY, now, ["GET", "POST"], TEST_RULE_ARN
        )
        assert result is False


class TestLoadStateFromS3:
    """Tests for the load_state_from_s3 function."""

    def test_loads_and_parses_json(self):
        """Test successful load and parse of state JSON."""
        state_data = {
            "activated_at": "2026-03-30T14:22:00+00:00",
            "original_http_methods": ["GET", "POST"],
            "rule_arn": TEST_RULE_ARN,
            "version": 1,
        }
        with mock.patch("subprocess.run") as mock_run:
            mock_result = mock.Mock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps(state_data)
            mock_run.return_value = mock_result

            result = load_state_from_s3(TEST_S3_BUCKET, TEST_S3_KEY)

            assert result == state_data

    def test_returns_none_when_object_not_found(self):
        """Test that None is returned when S3 object does not exist."""
        with mock.patch("subprocess.run") as mock_run:
            mock_result = mock.Mock()
            mock_result.returncode = 1
            mock_result.stderr = "An error occurred (NoSuchKey)"
            mock_run.return_value = mock_result

            result = load_state_from_s3(TEST_S3_BUCKET, TEST_S3_KEY)

            assert result is None

    def test_returns_none_on_json_decode_error(self):
        """Test that None is returned when JSON is invalid."""
        with mock.patch("subprocess.run") as mock_run:
            mock_result = mock.Mock()
            mock_result.returncode = 0
            mock_result.stdout = "not valid json"
            mock_run.return_value = mock_result

            result = load_state_from_s3(TEST_S3_BUCKET, TEST_S3_KEY)

            assert result is None

    def test_returns_none_on_subprocess_error(self):
        """Test that None is returned on subprocess error."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "aws", stderr="Error"
            )

            result = load_state_from_s3(TEST_S3_BUCKET, TEST_S3_KEY)

            assert result is None

    def test_returns_none_when_no_bucket_configured(self):
        """Test that None is returned when bucket is empty."""
        result = load_state_from_s3("", TEST_S3_KEY)
        assert result is None


class TestDeleteStateFromS3:
    """Tests for the delete_state_from_s3 function."""

    def test_deletes_object_via_aws_cli(self):
        """Test that correct aws s3 rm command is used."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0)

            result = delete_state_from_s3(TEST_S3_BUCKET, TEST_S3_KEY)

            assert result is True
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "s3" in cmd
            assert "rm" in cmd
            assert f"s3://{TEST_S3_BUCKET}/{TEST_S3_KEY}" in cmd

    def test_returns_false_on_error(self):
        """Test that False is returned on subprocess error."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "aws", stderr="Error"
            )

            result = delete_state_from_s3(TEST_S3_BUCKET, TEST_S3_KEY)

            assert result is False

    def test_returns_false_when_no_bucket(self):
        """Test that False is returned when bucket is empty."""
        result = delete_state_from_s3("", TEST_S3_KEY)
        assert result is False


class TestRestoreHttpMethodRestriction:
    """Tests for the restore_http_method_restriction function."""

    def test_restores_methods_successfully(self):
        """Test successful restoration of HTTP method restriction."""
        mock_rule = {
            "Conditions": [
                {"Field": "path-pattern", "Values": ["/*"]},
            ]
        }

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "get_listener_rule_details"
            ) as mock_get,
            mock.patch("subprocess.run") as mock_run,
        ):
            mock_get.return_value = mock_rule
            mock_result = mock.Mock()
            mock_result.stdout = "{}"
            mock_run.return_value = mock_result

            result = restore_http_method_restriction(
                TEST_RULE_ARN, ["GET", "POST"]
            )

            assert result is True
            # Verify the conditions include the HTTP method
            call_args = mock_run.call_args[0][0]
            conditions_json = call_args[call_args.index("--conditions") + 1]
            conditions = json.loads(conditions_json)
            http_method_conds = [
                c
                for c in conditions
                if c.get("Field") == "http-request-method"
            ]
            assert len(http_method_conds) == 1
            assert http_method_conds[0]["HttpRequestMethodConfig"][
                "Values"
            ] == ["GET", "POST"]

    def test_returns_false_when_rule_not_found(self):
        """Test that False is returned when rule cannot be retrieved."""
        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website."
            "get_listener_rule_details"
        ) as mock_get:
            mock_get.return_value = None

            result = restore_http_method_restriction(
                TEST_RULE_ARN, ["GET", "POST"]
            )

            assert result is False

    def test_idempotent_when_already_present(self):
        """Test that True is returned if HTTP method already present."""
        mock_rule = {
            "Conditions": [
                {
                    "Field": "http-request-method",
                    "HttpRequestMethodConfig": {"Values": ["GET", "POST"]},
                },
            ]
        }

        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website."
            "get_listener_rule_details"
        ) as mock_get:
            mock_get.return_value = mock_rule

            result = restore_http_method_restriction(
                TEST_RULE_ARN, ["GET", "POST"]
            )

            assert result is True

    def test_returns_false_on_subprocess_error(self):
        """Test that False is returned when AWS CLI command fails."""
        mock_rule = {
            "Conditions": [
                {"Field": "path-pattern", "Values": ["/*"]},
            ]
        }

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "get_listener_rule_details"
            ) as mock_get,
            mock.patch("subprocess.run") as mock_run,
        ):
            mock_get.return_value = mock_rule
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "aws", stderr="Error"
            )

            result = restore_http_method_restriction(
                TEST_RULE_ARN, ["GET", "POST"]
            )

            assert result is False


class TestCheckActivationTimeout:
    """Tests for the check_activation_timeout function."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset the global state before each test."""
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False
        yield
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False

    def test_deactivates_after_timeout(self):
        """Test that rule is restored after activation duration."""
        activated = datetime(2026, 3, 30, 12, 0, 0, tzinfo=UTC)
        state.phase = MonitorPhase.ACTIVATED
        state.activated_at = activated
        state.original_http_methods = ["GET", "POST"]

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website._now"
            ) as mock_now,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "restore_http_method_restriction"
            ) as mock_restore,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "delete_state_from_s3"
            ) as mock_delete,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "send_deactivation_email"
            ) as mock_email,
        ):
            # 1 hour + 1 second later
            mock_now.return_value = datetime(
                2026, 3, 30, 13, 0, 1, tzinfo=UTC
            )
            mock_restore.return_value = True

            check_activation_timeout()

            mock_restore.assert_called_once_with(
                monitor_website.LISTENER_RULE_ARN, ["GET", "POST"]
            )
            mock_delete.assert_called_once()
            mock_email.assert_called_once()
            assert state.phase == MonitorPhase.GRACE_PERIOD
            assert state.grace_period_start is not None
            assert state.activated_at is None
            assert state.original_http_methods is None
            assert state.consecutive_failures == 0

    def test_no_action_before_timeout(self):
        """Test that nothing happens before timeout expires."""
        activated = datetime(2026, 3, 30, 12, 0, 0, tzinfo=UTC)
        state.phase = MonitorPhase.ACTIVATED
        state.activated_at = activated
        state.original_http_methods = ["GET", "POST"]

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website._now"
            ) as mock_now,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "restore_http_method_restriction"
            ) as mock_restore,
        ):
            # Only 30 minutes later
            mock_now.return_value = datetime(
                2026, 3, 30, 12, 30, 0, tzinfo=UTC
            )

            check_activation_timeout()

            mock_restore.assert_not_called()
            assert state.phase == MonitorPhase.ACTIVATED

    def test_handles_restore_failure(self):
        """Test that state remains ACTIVATED on restore failure."""
        state.phase = MonitorPhase.ACTIVATED
        state.activated_at = datetime(
            2026, 3, 30, 12, 0, 0, tzinfo=UTC
        )
        state.original_http_methods = ["GET", "POST"]

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website._now"
            ) as mock_now,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "restore_http_method_restriction"
            ) as mock_restore,
        ):
            mock_now.return_value = datetime(
                2026, 3, 30, 13, 0, 1, tzinfo=UTC
            )
            mock_restore.return_value = False

            check_activation_timeout()

            assert state.phase == MonitorPhase.ACTIVATED

    def test_no_action_when_not_activated(self):
        """Test that nothing happens when not in ACTIVATED phase."""
        state.phase = MonitorPhase.MONITORING

        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website."
            "restore_http_method_restriction"
        ) as mock_restore:
            check_activation_timeout()

            mock_restore.assert_not_called()


class TestCheckGracePeriod:
    """Tests for the check_grace_period function."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset the global state before each test."""
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False
        yield
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False

    def test_transitions_to_monitoring_after_grace(self):
        """Test transition to MONITORING after grace period elapsed."""
        state.phase = MonitorPhase.GRACE_PERIOD
        state.grace_period_start = datetime(
            2026, 3, 30, 13, 0, 0, tzinfo=UTC
        )

        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website._now"
        ) as mock_now:
            # 5 min + 1 second later
            mock_now.return_value = datetime(
                2026, 3, 30, 13, 5, 1, tzinfo=UTC
            )

            check_grace_period()

            assert state.phase == MonitorPhase.MONITORING
            assert state.grace_period_start is None
            assert state.consecutive_failures == 0

    def test_no_action_during_grace(self):
        """Test that nothing happens during grace period."""
        state.phase = MonitorPhase.GRACE_PERIOD
        state.grace_period_start = datetime(
            2026, 3, 30, 13, 0, 0, tzinfo=UTC
        )

        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website._now"
        ) as mock_now:
            # Only 2 minutes later
            mock_now.return_value = datetime(
                2026, 3, 30, 13, 2, 0, tzinfo=UTC
            )

            check_grace_period()

            assert state.phase == MonitorPhase.GRACE_PERIOD

    def test_no_action_when_not_in_grace(self):
        """Test that nothing happens when not in GRACE_PERIOD phase."""
        state.phase = MonitorPhase.MONITORING

        check_grace_period()

        assert state.phase == MonitorPhase.MONITORING


class TestInitializeStateFromS3:
    """Tests for the initialize_state_from_s3 function."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset the global state before each test."""
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False
        yield
        state.consecutive_failures = 0
        state.phase = MonitorPhase.MONITORING
        state.activated_at = None
        state.original_http_methods = None
        state.grace_period_start = None
        state.test_mode = False

    @mock.patch(
        "knowledge_commons_profiles.cron.monitor_website.S3_STATE_BUCKET",
        TEST_S3_BUCKET,
    )
    def test_restores_active_state(self):
        """Test that active S3 state is restored on startup."""
        activated = datetime(2026, 3, 30, 12, 0, 0, tzinfo=UTC)
        saved_state = {
            "activated_at": activated.isoformat(),
            "original_http_methods": ["GET", "POST"],
            "rule_arn": monitor_website.LISTENER_RULE_ARN,
            "version": 1,
        }

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "load_state_from_s3"
            ) as mock_load,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website._now"
            ) as mock_now,
        ):
            mock_load.return_value = saved_state
            # 30 minutes later - still within window
            mock_now.return_value = datetime(
                2026, 3, 30, 12, 30, 0, tzinfo=UTC
            )

            initialize_state_from_s3()

            assert state.phase == MonitorPhase.ACTIVATED
            assert state.activated_at == activated
            assert state.original_http_methods == ["GET", "POST"]

    @mock.patch(
        "knowledge_commons_profiles.cron.monitor_website.S3_STATE_BUCKET",
        TEST_S3_BUCKET,
    )
    def test_restores_and_deactivates_expired_state(self):
        """Test that expired S3 state triggers immediate rule restoration."""
        activated = datetime(2026, 3, 30, 10, 0, 0, tzinfo=UTC)
        saved_state = {
            "activated_at": activated.isoformat(),
            "original_http_methods": ["GET", "POST"],
            "rule_arn": monitor_website.LISTENER_RULE_ARN,
            "version": 1,
        }

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "load_state_from_s3"
            ) as mock_load,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website._now"
            ) as mock_now,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "restore_http_method_restriction"
            ) as mock_restore,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "delete_state_from_s3"
            ) as mock_delete,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "send_deactivation_email"
            ) as mock_email,
        ):
            mock_load.return_value = saved_state
            # 3 hours later - well past window
            mock_now.return_value = datetime(
                2026, 3, 30, 13, 0, 0, tzinfo=UTC
            )
            mock_restore.return_value = True

            initialize_state_from_s3()

            mock_restore.assert_called_once_with(
                monitor_website.LISTENER_RULE_ARN, ["GET", "POST"]
            )
            mock_delete.assert_called_once()
            mock_email.assert_called_once()
            assert state.phase == MonitorPhase.GRACE_PERIOD
            assert state.grace_period_start is not None

    @mock.patch(
        "knowledge_commons_profiles.cron.monitor_website.S3_STATE_BUCKET",
        TEST_S3_BUCKET,
    )
    def test_no_action_when_no_s3_state(self):
        """Test that nothing happens when no S3 state exists."""
        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website."
            "load_state_from_s3"
        ) as mock_load:
            mock_load.return_value = None

            initialize_state_from_s3()

            assert state.phase == MonitorPhase.MONITORING

    @mock.patch(
        "knowledge_commons_profiles.cron.monitor_website.S3_STATE_BUCKET",
        "",
    )
    def test_no_action_when_no_bucket_configured(self):
        """Test that nothing happens when no S3 bucket is configured."""
        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website."
            "load_state_from_s3"
        ) as mock_load:
            initialize_state_from_s3()

            mock_load.assert_not_called()
            assert state.phase == MonitorPhase.MONITORING

    @mock.patch(
        "knowledge_commons_profiles.cron.monitor_website.S3_STATE_BUCKET",
        TEST_S3_BUCKET,
    )
    def test_ignores_mismatched_rule_arn(self):
        """Test that S3 state with mismatched rule_arn is ignored."""
        saved_state = {
            "activated_at": "2026-03-30T12:00:00+00:00",
            "original_http_methods": ["GET", "POST"],
            "rule_arn": "arn:aws:wrong-arn",
            "version": 1,
        }

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "load_state_from_s3"
            ) as mock_load,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website._now"
            ) as mock_now,
        ):
            mock_load.return_value = saved_state
            mock_now.return_value = datetime(
                2026, 3, 30, 12, 30, 0, tzinfo=UTC
            )

            initialize_state_from_s3()

            assert state.phase == MonitorPhase.MONITORING

    @mock.patch(
        "knowledge_commons_profiles.cron.monitor_website.S3_STATE_BUCKET",
        TEST_S3_BUCKET,
    )
    def test_handles_restore_failure_on_expired(self):
        """Test that failed restore on expired state sets ACTIVATED."""
        activated = datetime(2026, 3, 30, 10, 0, 0, tzinfo=UTC)
        saved_state = {
            "activated_at": activated.isoformat(),
            "original_http_methods": ["GET", "POST"],
            "rule_arn": monitor_website.LISTENER_RULE_ARN,
            "version": 1,
        }

        with (
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "load_state_from_s3"
            ) as mock_load,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website._now"
            ) as mock_now,
            mock.patch(
                "knowledge_commons_profiles.cron.monitor_website."
                "restore_http_method_restriction"
            ) as mock_restore,
        ):
            mock_load.return_value = saved_state
            mock_now.return_value = datetime(
                2026, 3, 30, 13, 0, 0, tzinfo=UTC
            )
            mock_restore.return_value = False

            initialize_state_from_s3()

            assert state.phase == MonitorPhase.ACTIVATED
            assert state.activated_at == activated
            assert state.original_http_methods == ["GET", "POST"]


class TestSendDeactivationEmail:
    """Tests for the send_deactivation_email function."""

    def test_sends_with_correct_parameters(self):
        """Test that deactivation email sends correct content."""
        with mock.patch(
            "knowledge_commons_profiles.cron.monitor_website."
            "SparkPostEmailClient"
        ) as mock_client_class:
            mock_client = mock.Mock()
            mock_client.send_email.return_value = {"success": True}
            mock_client_class.return_value = mock_client

            result = send_deactivation_email()

            mock_client.send_email.assert_called_once()
            call_kwargs = mock_client.send_email.call_args[1]

            assert call_kwargs["from_email"] == "system@hcommons.org"
            expected_subject = (
                "DDOS Protection has been automatically deactivated"
            )
            assert call_kwargs["subject"] == expected_subject
            assert "restored" in call_kwargs["html_content"].lower()
            assert call_kwargs["tags"] == ["system", "ddos"]
            assert result == {"success": True}
