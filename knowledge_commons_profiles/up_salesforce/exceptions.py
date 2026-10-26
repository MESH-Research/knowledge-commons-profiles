"""
Exceptions raised by the UP Salesforce External Client App integration.
"""


class UPSalesforceError(Exception):
    """Base error for the UP Salesforce integration."""


class UPSalesforceConfigurationError(UPSalesforceError):
    """Raised when the consumer key/secret or URLs are not configured."""


class UPSalesforceAuthError(UPSalesforceError):
    """Raised when Salesforce refuses to issue an access token."""
