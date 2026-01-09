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


@dataclass
class MonitorState:
    """State tracking for the monitor."""

    consecutive_failures: int = 0
    rule_modified: bool = False
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
            "listener rule that blocks the members routes. "
            "When the site has recovered, you should manually "
            "remove this.</p>"
        ),
        text_content=(
            "Attack Blocked. "
            "The system has automatically engaged the AWS ALB "
            "listener rule that blocks the members routes. "
            "When the site has recovered, you should manually "
            "remove this."
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


def handle_site_up():
    """Handle the case when the website is up."""
    state.consecutive_failures = 0

    if state.rule_modified:
        logger.info("Website is back up. Rule modification will remain.")
        logger.info(
            "Note: You may want to manually restore the HTTP "
            "method restriction when ready."
        )


def handle_site_down():
    """Handle the case when the website is down."""
    state.consecutive_failures += 1
    logger.warning(
        "Website is down. Consecutive failures: %s",
        state.consecutive_failures,
    )

    if (
        state.consecutive_failures >= SITE_DOWN_THRESHOLD
        and not state.rule_modified
    ):
        logger.warning(
            "Website down for %s checks. Removing HTTP method restriction...",
            state.consecutive_failures,
        )

        # Get and store original HTTP methods before modifying
        rule = get_listener_rule_details(LISTENER_RULE_ARN)
        if rule:
            for condition in rule.get("Conditions", []):
                if condition.get("Field") == "http-request-method":
                    _ = condition.get("Values", ["GET", "POST"])
                    break

        if remove_http_method_restriction(LISTENER_RULE_ARN):
            state.rule_modified = True
            logger.info("HTTP method restriction removed successfully")
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

    try:
        while True:
            is_up = check_website_status(WEBSITE_URL)

            if is_up:
                handle_site_up()
            else:
                handle_site_down()

            # Wait before next check
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
