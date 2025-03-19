import django_saml2_auth.views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.urls import path
from django.views import defaults as default_views

urlpatterns = [
    # These are the SAML2 related URLs. (required)
    path("^sso/", include("django_saml2_auth.urls")),
    # The following line will replace the default user login with
    # SAML2 (optional). If you want to specific the after-login-redirect-URL,
    # use parameter "?next=/the/path/you/want" with this view.
    path("accounts/login/", django_saml2_auth.views.signin),
    # The following line will replace the admin login with SAML2 (optional)
    # If you want to specific the after-login-redirect-URL, use parameter
    # "?next=/the/path/you/want" with this view.
    path("admin/login/", django_saml2_auth.views.signin),
    path("select2/", include("django_select2.urls")),
    path(settings.ADMIN_URL, admin.site.urls),
    path("profile/", include("knowledge_commons_profiles.newprofile.urls")),
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]


if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]
