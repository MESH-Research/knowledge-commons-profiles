"""
Test suite for website uptime monitor module.
"""

import json
import subprocess
from unittest import mock

import pytest
import requests

from knowledge_commons_profiles.cron import monitor_website
from knowledge_commons_profiles.cron.monitor_website import HTTP_STATUS_OK_MAX
from knowledge_commons_profiles.cron.monitor_website import HTTP_STATUS_OK_MIN
from knowledge_commons_profiles.cron.monitor_website import MonitorState
from knowledge_commons_profiles.cron.monitor_website import build_cmd
from knowledge_commons_profiles.cron.monitor_website import check_website_status
from knowledge_commons_profiles.cron.monitor_website import (
    get_listener_rule_details,
)
from knowledge_commons_profiles.cron.monitor_website import handle_site_down
from knowledge_commons_profiles.cron.monitor_website import handle_site_up
from knowledge_commons_profiles.cron.monitor_website import (
    normalize_condition_format,
)
from knowledge_commons_profiles.cron.monitor_website import (
    remove_http_method_restriction,
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


class TestMonitorState:
    """Tests for the MonitorState dataclass."""

    def test_default_values(self):
        """Test that MonitorState has correct default values."""
        monitor_state = MonitorState()
        assert monitor_state.consecutive_failures == 0
        assert monitor_state.rule_modified is False
        assert monitor_state.test_mode is False

    def test_custom_values(self):
        """Test that MonitorState accepts custom values."""
        monitor_state = MonitorState(
            consecutive_failures=TEST_FAILURE_COUNT,
            rule_modified=True,
            test_mode=True,
        )
        assert monitor_state.consecutive_failures == TEST_FAILURE_COUNT
        assert monitor_state.rule_modified is True
        assert monitor_state.test_mode is True


class TestCheckWebsiteStatus:
    """Tests for the check_website_status function."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset the global state before each test."""
        state.consecutive_failures = 0
        state.rule_modified = False
        state.test_mode = False
        yield
        # Reset after test too
        state.consecutive_failures = 0
        state.rule_modified = False
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
        state.rule_modified = False
        state.test_mode = False
        yield
        state.consecutive_failures = 0
        state.rule_modified = False
        state.test_mode = False

    def test_resets_consecutive_failures(self):
        """Test that handle_site_up resets the failure counter."""
        state.consecutive_failures = TEST_FAILURE_COUNT

        handle_site_up()

        assert state.consecutive_failures == 0

    def test_does_not_reset_rule_modified_flag(self):
        """Test that rule_modified flag persists after site comes back up."""
        state.rule_modified = True

        handle_site_up()

        # Rule modification should persist - requires manual restoration
        assert state.rule_modified is True


class TestHandleSiteDown:
    """Tests for the handle_site_down function."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset the global state before each test."""
        state.consecutive_failures = 0
        state.rule_modified = False
        state.test_mode = False
        yield
        state.consecutive_failures = 0
        state.rule_modified = False
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
            mock_remove.return_value = True

            handle_site_down()

            mock_remove.assert_called_once()
            mock_email.assert_called_once()
            assert state.rule_modified is True

    def test_does_not_modify_rule_if_already_modified(self):
        """Test that rule is not modified twice."""
        state.consecutive_failures = monitor_website.SITE_DOWN_THRESHOLD
        state.rule_modified = True

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
            assert state.rule_modified is False
