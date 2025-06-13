"""
Common email functions

"""

import logging
import socket
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import BadHeaderError
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_knowledge_commons_email(
    recipient_email, context_data=None, template_file=""
):
    """
    Send the Knowledge Commons HTML email template
    """
    # Default context data
    if context_data is None:
        context_data = {}

    # Add any default context variables
    default_context = {
        "email": recipient_email,
    }
    default_context.update(context_data)

    # Render the HTML template
    html_content = render_to_string(
        template_name=template_file, context=default_context
    )

    # Create a plain text version by stripping HTML tags
    text_content = strip_tags(html_content)

    # Email details
    subject = "Welcome to Knowledge Commons"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = [recipient_email]

    # Create the email message
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,  # Plain text version
        from_email=from_email,
        to=to_email,
    )

    # Attach the HTML version
    msg.attach_alternative(html_content, "text/html")

    # Send the email
    success = True

    try:
        msg.send()
    except BadHeaderError:
        # Invalid header found in email
        message = f"BadHeaderError when sending email to {recipient_email}"
        logger.exception(message)
        success = False
    except SMTPException:
        # SMTP-related errors (authentication, connection, etc.)
        message = f"SMTPException when sending email to {recipient_email}"
        logger.exception(message)
        success = False
    except socket.gaierror:
        # DNS lookup failures
        message = f"DNS lookup error when sending email to {recipient_email}"
        logger.exception(message)
        success = False
    except TimeoutError:
        # Connection timeout
        message = f"Connection timeout when sending email to {recipient_email}"
        logger.exception(message)
        success = False
    except ConnectionRefusedError:
        # Connection refused by mail server
        message = f"Connection refused when sending email to {recipient_email}"
        logger.exception(message)
        success = False
    except OSError:
        # Other network-related errors
        message = f"Network error when sending email to {recipient_email}"
        logger.exception(message)
        success = False
    except Exception:
        message = f"Error sending email for template {template_file}"
        logger.exception(message)
        success = False

    return success


def sanitize_email_for_dev(email):
    """
    Sanitize email by replacing martin@martineve.com with martin@eve.gd
    :param email: the input email
    :return: a replaced email
    """
    return email.replace("martin@martineve.com", "martin@eve.gd")
