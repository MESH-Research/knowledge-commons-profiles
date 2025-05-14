"""OAuth initializer"""

from authlib.integrations.django_client import OAuth
from django.conf import settings

oauth = OAuth()

oauth.register(
    name="cilogon",
    client_id=settings.CILOGON_CLIENT_ID,
    client_secret=settings.CILOGON_CLIENT_SECRET,
    server_metadata_url="https://cilogon.org/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile org.cilogon.userinfo offline_access"
    },
)
