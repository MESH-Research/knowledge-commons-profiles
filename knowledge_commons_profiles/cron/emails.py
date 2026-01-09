"""
SparkPost Email Sending Module

This module provides functionality to send emails to multiple recipients
using SparkPost.
"""

import logging

import environ
import requests

env = environ.Env()
logger = logging.getLogger(__name__)

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
