"""
Website Uptime Monitor with AWS ALB Rule Modification

This script monitors the uptime of a website every 5 minutes.
If the site is down, it removes the HTTP request method restriction
from a specified AWS ALB listener rule.
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from enum import Enum
from typing import Any

import environ
import requests

log_formatter = logging.Formatter(
    "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
)
root_logger = logging.getLogger()

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(console_handler)

env = environ.Env()
logger = logging.getLogger(__name__)

# Configuration
WEBSITE_URL = env("CHECK_WEBSITE", default="https://hcommons.org")
LISTENER_RULE_ARN = (
    "arn:aws:elasticloadbalancing:us-east-1:755997884632:"
    "listener-rule/app/hcommons-prod-alb/cd92f60f938442a3/7bf51009f05e0d44/"
    "a33ced76e84ab9c3"
)
CHECK_INTERVAL = 60  # seconds
REQUEST_TIMEOUT = 10  # seconds
SITE_DOWN_THRESHOLD = 2  # Number of consecutive failures before taking action

# Timing constants
ACTIVATION_DURATION = 3600  # seconds (1 hour) before auto-deactivation
GRACE_PERIOD_DURATION = 300  # seconds (5 minutes) after deactivation

# S3 configuration
S3_STATE_BUCKET = env("MONITOR_S3_BUCKET", default="")
S3_STATE_KEY = "monitor/alb-rule-state.json"

# HTTP status code ranges
HTTP_STATUS_OK_MIN = 200
HTTP_STATUS_OK_MAX = 400

RECIPIENTS = [
    "martin@eve.gd",
    "eve@msu.edu",
    "tzouris@msu.edu",
    "bonnie@msu.edu",
    "scottia4@msu.edu",
]

# SparkPost API endpoint (defaults for testing)
SPARKPOST_API_URL = env("SPARKPOST_API_URL", default="")
SPARKPOST_API_KEY = env("SPARKPOST_API_KEY", default="")


class SparkPostEmailClient:
    """Client for sending emails via SparkPost API."""

    def __init__(self):
        """Initialize the SparkPost email client."""
        self.api_key = SPARKPOST_API_KEY
        self.base_url = SPARKPOST_API_URL
        self.headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

    def send_email(  # noqa: PLR0913
        self,
        from_email: str,
        from_name: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
        recipients: list[str] | None = None,
        recipient_objects: list[dict] | None = None,
        reply_to: str | None = None,
        tags: list[str] | None = None,
        *,
        track_opens: bool = True,
        track_clicks: bool = True,
    ) -> dict:
        """
        Send an email to one or multiple recipients.

        Args:
            from_email: Sender's email address
            from_name: Sender's display name
            subject: Email subject line
            html_content: HTML body of the email
            text_content: Plain text body of the email (optional)
            recipients: List of recipient email addresses (simple format)
            recipient_objects: List of recipient objects with advanced options
            reply_to: Reply-to email address
            tags: List of tags for tracking and organization
            track_opens: Whether to track email opens
            track_clicks: Whether to track link clicks

        Returns:
            Dictionary containing the API response
        """
        # Build the recipients list
        if recipients:
            # Simple format: just email addresses
            recipients_list = [
                {"address": {"email": email}} for email in recipients
            ]
        elif recipient_objects:
            # Advanced format: recipient objects with additional metadata
            recipients_list = recipient_objects
        else:
            msg = "Either 'recipients' or 'recipient_objects' must be provided"
            raise ValueError(msg)

        # Build the email payload
        payload = {
            "options": {
                "open_tracking": track_opens,
                "click_tracking": track_clicks,
            },
            "content": {
                "from": {
                    "email": from_email,
                    "name": from_name,
                },
                "subject": subject,
                "html": html_content,
            },
            "recipients": recipients_list,
        }

        # Add optional fields
        if text_content:
            payload["content"]["text"] = text_content

        if reply_to:
            payload["content"]["reply_to"] = reply_to

        if tags:
            payload["tags"] = tags

        # Make the API request
        try:
            response = requests.post(
                f"{self.base_url}/transmissions",
                headers=self.headers,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to send email via SparkPost")
            return {
                "success": False,
                "error": "Request failed",
            }


class MonitorPhase(Enum):
    """Phases of the monitor state machine."""

    MONITORING = "monitoring"
    ACTIVATED = "activated"
    GRACE_PERIOD = "grace_period"


@dataclass
class MonitorState:
    """State tracking for the monitor."""

    consecutive_failures: int = 0
    phase: MonitorPhase = MonitorPhase.MONITORING
    activated_at: datetime | None = None
    original_http_methods: list[str] | None = field(default=None)
    grace_period_start: datetime | None = None
    test_mode: bool = False


# Global state instance
state = MonitorState()


def check_website_status(url: str) -> bool:
    """
    Check if the website is up by making an HTTP request.

    Args:
        url: The website URL to check

    Returns:
        True if the site is up, False otherwise
    """
    # In test mode, always return False to simulate site being down
    if state.test_mode:
        logger.info("Website check: %s - TEST MODE - Simulating DOWN", url)
        return False

    try:
        response = requests.get(
            url, timeout=REQUEST_TIMEOUT, allow_redirects=True
        )
    except requests.exceptions.Timeout:
        logger.warning("Website check timeout: %s", url)
        return False
    except requests.exceptions.ConnectionError:
        logger.warning("Website connection error: %s", url)
        return False
    except requests.exceptions.RequestException:
        logger.exception("Website check failed: %s", url)
        return False

    # Consider 2xx and 3xx status codes as "up"
    is_up = HTTP_STATUS_OK_MIN <= response.status_code < HTTP_STATUS_OK_MAX
    status = "UP" if is_up else "DOWN"
    logger.info(
        "Website check: %s - Status code: %s - %s",
        url,
        response.status_code,
        status,
    )
    return is_up


def get_listener_rule_details(rule_arn: str) -> dict[str, Any] | None:
    """
    Retrieve the current configuration of the ALB listener rule.

    Args:
        rule_arn: The ARN of the listener rule

    Returns:
        Dictionary containing the rule details, or None if retrieval fails
    """
    try:
        cmd = [
            "aws",
            "elbv2",
            "describe-rules",
            "--rule-arns",
            rule_arn,
            "--output",
            "json",
        ]
        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.exception("AWS CLI error retrieving rule: %s", e.stderr)
        return None
    except json.JSONDecodeError:
        logger.exception("Failed to parse AWS response")
        return None

    if data.get("Rules"):
        rule = data["Rules"][0]
        logger.info("Retrieved listener rule details")
        return rule
    logger.error("No rules found for the specified ARN")
    return None


def normalize_condition_format(condition: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a condition to use the new config format.

    Strips the old 'Values' field and keeps only the 'XxxConfig' format.

    Args:
        condition: The condition to normalize

    Returns:
        Normalized condition dictionary with only Field and XxxConfig
    """
    field_name = condition.get("Field")

    # Find if there's already a Config key
    config_key = None
    for key in condition:
        if key.endswith("Config"):
            config_key = key
            break

    # If condition has a Config key, return only Field + Config (strip Values)
    if config_key:
        return {"Field": field_name, config_key: condition[config_key]}

    # Convert old 'Values' format to new 'XxxConfig' format
    values = condition.get("Values", [])

    field_config_map = {
        "path-pattern": "PathPatternConfig",
        "host-header": "HostHeaderConfig",
        "http-request-method": "HttpRequestMethodConfig",
        "source-ip": "SourceIpConfig",
        "query-string": "QueryStringConfig",
    }

    if field_name in field_config_map:
        config_name = field_config_map[field_name]
        return {"Field": field_name, config_name: {"Values": values}}

    # For unknown fields, return as-is
    return condition


def remove_http_method_restriction(rule_arn: str) -> bool:
    """
    Remove the HTTP request method restriction from the ALB listener rule.

    Preserves all other conditions (like Path conditions).

    Args:
        rule_arn: The ARN of the listener rule

    Returns:
        True if successful, False otherwise
    """
    # Get current rule details
    rule = get_listener_rule_details(rule_arn)
    if not rule:
        logger.error("Could not retrieve rule details")
        return False

    # Get current conditions and filter out HttpRequestMethodConfig
    current_conditions = rule.get("Conditions", [])
    new_conditions = [
        cond
        for cond in current_conditions
        if cond.get("Field") != "http-request-method"
    ]

    # If no HTTP method condition was found, nothing to do
    if len(new_conditions) == len(current_conditions):
        logger.info("No HTTP request method restriction found on rule")
        return False

    # Normalize all conditions to use the new Config format
    normalized_conditions = [
        normalize_condition_format(cond) for cond in new_conditions
    ]

    # Prepare the modify-rule command
    cmd = build_cmd(normalized_conditions, rule_arn)

    logger.info("Removing HTTP request method restriction from rule")
    try:
        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        logger.exception("AWS CLI error modifying rule: %s", e.stderr)
        return False

    logger.info("Successfully removed HTTP request method restriction")
    logger.debug("AWS response: %s", result.stdout)
    return True


def send_email():
    """
    Send email to the desired recipients.

    Returns:
        The JSON response from the SparkPost request
    """
    client = SparkPostEmailClient()

    response = client.send_email(
        from_email="system@hcommons.org",
        from_name="Knowledge Commons System",
        subject="DDOS Protection has been activated",
        html_content=(
            "<h1>Attack Blocked</h1>"
            "<p>The system has automatically engaged the AWS ALB "
            "listener rule that blocks the members routes.</p>"
            "<p>This protection will be <strong>automatically removed "
            "after 1 hour</strong>. If the site is still down at that "
            "point, it will re-activate if downtime continues.</p>"
        ),
        text_content=(
            "Attack Blocked. "
            "The system has automatically engaged the AWS ALB "
            "listener rule that blocks the members routes. "
            "This protection will be automatically removed after 1 hour. "
            "If the site is still down at that point, it will re-activate "
            "if downtime continues."
        ),
        recipients=RECIPIENTS,
        tags=["system", "ddos"],
    )

    logger.info("Email response: %s", response)
    return response


def build_cmd(new_conditions: list[Any], rule_arn: str) -> list[str]:
    """
    Build an AWS command that instates new rules.

    Args:
        new_conditions: the new conditions
        rule_arn: the rule ARN

    Returns:
        A list of strings with command params
    """
    return [
        "aws",
        "elbv2",
        "modify-rule",
        "--rule-arn",
        rule_arn,
        "--conditions",
        json.dumps(new_conditions),
    ]


def _now() -> datetime:
    """Return current UTC time. Extracted for testability."""
    return datetime.now(UTC)


def save_state_to_s3(
    bucket: str,
    key: str,
    activated_at: datetime,
    original_http_methods: list[str],
    rule_arn: str,
) -> bool:
    """Save activation state to S3 for persistence across restarts."""
    if not bucket:
        logger.warning("No S3 bucket configured, skipping state save")
        return False

    state_data = {
        "activated_at": activated_at.isoformat(),
        "original_http_methods": original_http_methods,
        "rule_arn": rule_arn,
        "version": 1,
    }

    cmd = [
        "aws", "s3", "cp", "-",
        f"s3://{bucket}/{key}",
        "--content-type", "application/json",
    ]

    try:
        subprocess.run(  # noqa: S603
            cmd,
            input=json.dumps(state_data),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.exception("Failed to save state to S3: %s", e.stderr)
        return False

    logger.info("Saved activation state to S3")
    return True


def load_state_from_s3(bucket: str, key: str) -> dict | None:
    """Load activation state from S3. Returns None if no state exists."""
    if not bucket:
        return None

    cmd = ["aws", "s3", "cp", f"s3://{bucket}/{key}", "-"]

    try:
        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, check=False
        )
    except subprocess.CalledProcessError:
        logger.exception("Failed to load state from S3")
        return None

    if result.returncode != 0:
        logger.info("No existing state found in S3")
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.exception("Failed to parse S3 state JSON")
        return None


def delete_state_from_s3(bucket: str, key: str) -> bool:
    """Delete activation state from S3 after deactivation."""
    if not bucket:
        return False

    cmd = ["aws", "s3", "rm", f"s3://{bucket}/{key}"]

    try:
        subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        logger.exception("Failed to delete state from S3: %s", e.stderr)
        return False

    logger.info("Deleted activation state from S3")
    return True


def restore_http_method_restriction(
    rule_arn: str, http_methods: list[str]
) -> bool:
    """Restore the HTTP request method restriction on the ALB listener rule."""
    rule = get_listener_rule_details(rule_arn)
    if not rule:
        logger.error("Could not retrieve rule details for restoration")
        return False

    current_conditions = rule.get("Conditions", [])

    # Check if HTTP method condition already exists (idempotency)
    for cond in current_conditions:
        if cond.get("Field") == "http-request-method":
            logger.info("HTTP method restriction already present")
            return True

    # Add the HTTP method condition back
    http_method_condition = {
        "Field": "http-request-method",
        "HttpRequestMethodConfig": {"Values": http_methods},
    }
    new_conditions = [
        normalize_condition_format(cond) for cond in current_conditions
    ] + [http_method_condition]

    cmd = build_cmd(new_conditions, rule_arn)

    logger.info("Restoring HTTP request method restriction on rule")
    try:
        subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        logger.exception("AWS CLI error restoring rule: %s", e.stderr)
        return False

    logger.info("Successfully restored HTTP request method restriction")
    return True


def send_deactivation_email():
    """Send email notifying that DDOS protection has been deactivated."""
    client = SparkPostEmailClient()

    response = client.send_email(
        from_email="system@hcommons.org",
        from_name="Knowledge Commons System",
        subject="DDOS Protection has been automatically deactivated",
        html_content=(
            "<h1>Protection Deactivated</h1>"
            "<p>The AWS ALB listener rule that blocks the members routes "
            "has been automatically restored after 1 hour. "
            "Normal monitoring has resumed after a brief grace period.</p>"
            "<p>If the site is still experiencing issues, the protection "
            "will re-activate automatically if downtime is detected.</p>"
        ),
        text_content=(
            "Protection Deactivated. "
            "The AWS ALB listener rule that blocks the members routes "
            "has been automatically restored after 1 hour. "
            "Normal monitoring has resumed after a brief grace period. "
            "If the site is still experiencing issues, the protection "
            "will re-activate automatically if downtime is detected."
        ),
        recipients=RECIPIENTS,
        tags=["system", "ddos"],
    )

    logger.info("Deactivation email response: %s", response)
    return response


def check_activation_timeout():
    """Check if the activation has exceeded the timeout and deactivate."""
    if state.phase != MonitorPhase.ACTIVATED or state.activated_at is None:
        return

    elapsed = (_now() - state.activated_at).total_seconds()
    if elapsed < ACTIVATION_DURATION:
        return

    logger.info(
        "Activation duration exceeded (%s seconds). Restoring rule...",
        elapsed,
    )

    if restore_http_method_restriction(
        LISTENER_RULE_ARN, state.original_http_methods
    ):
        logger.info("HTTP method restriction restored successfully")
        delete_state_from_s3(S3_STATE_BUCKET, S3_STATE_KEY)
        send_deactivation_email()
        state.phase = MonitorPhase.GRACE_PERIOD
        state.grace_period_start = _now()
        state.activated_at = None
        state.original_http_methods = None
        state.consecutive_failures = 0
    else:
        logger.error("Failed to restore HTTP method restriction")


def check_grace_period():
    """Check if the grace period has elapsed and return to monitoring."""
    if (
        state.phase != MonitorPhase.GRACE_PERIOD
        or state.grace_period_start is None
    ):
        return

    elapsed = (_now() - state.grace_period_start).total_seconds()
    if elapsed >= GRACE_PERIOD_DURATION:
        logger.info("Grace period complete. Resuming normal monitoring.")
        state.phase = MonitorPhase.MONITORING
        state.grace_period_start = None
        state.consecutive_failures = 0


def initialize_state_from_s3():
    """Check S3 for existing activation state (handles ECS restarts)."""
    if not S3_STATE_BUCKET:
        logger.warning("No S3 bucket configured, state persistence disabled")
        return

    saved = load_state_from_s3(S3_STATE_BUCKET, S3_STATE_KEY)
    if saved is None:
        logger.info("No existing activation state found in S3")
        return

    if saved.get("rule_arn") != LISTENER_RULE_ARN:
        logger.warning("S3 state rule_arn mismatch, ignoring")
        return

    activated_at = datetime.fromisoformat(saved["activated_at"])
    original_methods = saved.get("original_http_methods", ["GET", "POST"])
    elapsed = (_now() - activated_at).total_seconds()

    if elapsed >= ACTIVATION_DURATION:
        logger.info(
            "Found expired activation state (%s seconds ago). "
            "Restoring rule...",
            elapsed,
        )
        if restore_http_method_restriction(LISTENER_RULE_ARN, original_methods):
            delete_state_from_s3(S3_STATE_BUCKET, S3_STATE_KEY)
            send_deactivation_email()
            state.phase = MonitorPhase.GRACE_PERIOD
            state.grace_period_start = _now()
        else:
            logger.error("Failed to restore rule from expired S3 state")
            state.phase = MonitorPhase.ACTIVATED
            state.activated_at = activated_at
            state.original_http_methods = original_methods
    else:
        logger.info(
            "Found active activation state (%s seconds ago). "
            "Resuming activated state.",
            elapsed,
        )
        state.phase = MonitorPhase.ACTIVATED
        state.activated_at = activated_at
        state.original_http_methods = original_methods


def handle_site_up():
    """Handle the case when the website is up."""
    state.consecutive_failures = 0


def handle_site_down():
    """Handle the case when the website is down."""
    state.consecutive_failures += 1
    logger.warning(
        "Website is down. Consecutive failures: %s",
        state.consecutive_failures,
    )

    if (
        state.consecutive_failures >= SITE_DOWN_THRESHOLD
        and state.phase == MonitorPhase.MONITORING
    ):
        logger.warning(
            "Website down for %s checks. Removing HTTP method restriction...",
            state.consecutive_failures,
        )

        # Get and store original HTTP methods before modifying
        rule = get_listener_rule_details(LISTENER_RULE_ARN)
        original_methods = ["GET", "POST"]
        if rule:
            for condition in rule.get("Conditions", []):
                if condition.get("Field") == "http-request-method":
                    config = condition.get("HttpRequestMethodConfig", {})
                    original_methods = config.get(
                        "Values",
                        condition.get("Values", ["GET", "POST"]),
                    )
                    break

        if remove_http_method_restriction(LISTENER_RULE_ARN):
            now = _now()
            state.phase = MonitorPhase.ACTIVATED
            state.activated_at = now
            state.original_http_methods = original_methods
            logger.info("HTTP method restriction removed successfully")

            save_state_to_s3(
                S3_STATE_BUCKET,
                S3_STATE_KEY,
                now,
                original_methods,
                LISTENER_RULE_ARN,
            )

            send_email()
        else:
            logger.error("Failed to remove HTTP method restriction")


def monitor_loop():
    """
    Main monitoring loop that runs indefinitely.

    Checks website status every CHECK_INTERVAL seconds.
    """
    logger.info("Starting website monitor for %s", WEBSITE_URL)
    logger.info("Check interval: %s seconds", CHECK_INTERVAL)
    logger.info("Listener rule ARN: %s", LISTENER_RULE_ARN)
    if state.test_mode:
        logger.warning("TEST MODE ENABLED - Site will be simulated as DOWN")

    initialize_state_from_s3()

    try:
        while True:
            if state.phase == MonitorPhase.MONITORING:
                is_up = check_website_status(WEBSITE_URL)
                if is_up:
                    handle_site_up()
                else:
                    handle_site_down()
            elif state.phase == MonitorPhase.ACTIVATED:
                check_activation_timeout()
            elif state.phase == MonitorPhase.GRACE_PERIOD:
                check_grace_period()

            logger.info("Next check in %s seconds...", CHECK_INTERVAL)
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Monitor interrupted by user")
        sys.exit(0)


def main():
    """Entry point for the monitor script."""
    parser = argparse.ArgumentParser(
        description="Website uptime monitor with AWS ALB rule modification"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: simulate the website being inaccessible",
    )
    args = parser.parse_args()

    state.test_mode = args.test

    monitor_loop()


if __name__ == "__main__":
    main()
