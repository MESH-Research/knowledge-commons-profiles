# ruff: noqa: E501
"""Base settings to build other settings files upon."""
import threading
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# knowledge_commons_profiles/
APPS_DIR = BASE_DIR / "knowledge_commons_profiles"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "UTC"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
# https://docs.djangoproject.com/en/dev/ref/settings/#languages
# from django.utils.translation import gettext_lazy as _
# LANGUAGES = [
#     ('en', _('English')),
#     ('fr-fr', _('French')),
#     ('pt-br', _('Portuguese')),
# ]
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(BASE_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

DATABASES = {
    "default": env.db("DATABASE_URL", ""),
    "wordpress_dev": env.db("WORDPRESS_DATABASE_URL", ""),
}

DATABASE_ROUTERS = [
    "knowledge_commons_profiles.newprofile.wordpress_router.ReadWriteRouter"
]

# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.admin",
    "django.forms",
]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "rest_framework",
    "tinymce",
    "django_select2",
    "authlib.integrations.django_client",
    "drf_yasg",
]

LOCAL_APPS = [
    "knowledge_commons_profiles.cilogon.apps.CILogonConfig",
    "knowledge_commons_profiles.newprofile.apps.NewProfileConfig",
    "knowledge_commons_profiles.rest_api.apps.RestAPIConfig",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {
    "sites": "knowledge_commons_profiles.contrib.sites.migrations",
}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "knowledge_commons_profiles.cilogon.middleware.GarbageCollectionMiddleware",
    "knowledge_commons_profiles.cilogon.middleware.AutoRefreshTokenMiddleware",
    "knowledge_commons_profiles.common.middleware.RequestMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [str(APPS_DIR / "static")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(APPS_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        "DIRS": [str(APPS_DIR / "templates")],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "knowledge_commons_profiles.newprofile.context_processors."
                "cc_search",
            ],
        },
    },
]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [("""Martin Paul Eve""", "evemarti@msu.edu")]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG" if DEBUG else "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "inotify_buffer": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "watchdog": {
            "level": "WARNING",
            "propagate": False,
        },
        "watchdog.observers": {
            "level": "WARNING",
            "propagate": False,
        },
        "debug_toolbar": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
    },
    "root": {"level": "DEBUG" if DEBUG else "INFO", "handlers": ["console"]},
}

# Your stuff...
# ------------------------------------------------------------------------------

TINYMCE_DEFAULT_CONFIG = {
    "license_key": "gpl",
    "height": 360,
    "width": "100%",
    "custom_undo_redo_levels": 20,
    "selector": "textarea",
    "theme": "silver",
    "plugins": """
        save link image media preview
        table code lists fullscreen insertdatetime nonbreaking
        directionality searchreplace wordcount visualblocks
        visualchars code fullscreen autolink lists charmap
        anchor pagebreak
        """,
    "toolbar1": """
        fullscreen preview bold italic underline | fontselect,
        fontsizeselect | forecolor backcolor | alignleft alignright |
        aligncenter alignjustify | indent outdent | bullist numlist table |
        | link | code
        """,
    "contextmenu": "formats | link image",
    "menubar": False,
    "statusbar": True,
    "promotion": False,
    "forced_root_block": " ",
}

SELECT2_CACHE_BACKEND = "select2"

TINYMCE_JS_URL = STATIC_URL + "tinymcelocal/js/tinymce/tinymce.min.js"

REDIRECT_FIELD_NAME = "redirect_to"

PROFILE_FIELDS_LEFT = [
    "about_user",
    "education",
    "publications",
    "projects",
    "works",
    "blog_posts",
    "mastodon_feed",
]

PROFILE_FIELDS_RIGHT = [
    "academic_interests",
    "commons_groups",
    "commons_activity",
    "commons_sites",
]

LOGIN_URL = "/login/"

CITATION_STYLES = {
    "ACM": "styles/association-for-computing-machinery.csl",
    "APA": "styles/apa.csl",
    "APS": "styles/american-physics-society.csl",
    "Chicago": "styles/chicago-author-date.csl",
    "Harvard": "harvard1",
    "IEEE": "styles/ieee.csl",
    "JACS": "styles/journal-of-the-american-college-of-surgeons.csl",
    "MHRA": "styles/modern-humanities-research-association.csl",
    "MLA": "styles/modern-language-association.csl",
    "Vancouver": "styles/vancouver.csl",
}

# colors to use for stacked bar charts
CHART_COLORS = [
    "#1C4036",
    "#669999",
    "#C9E3DB",
    "#F5F5EB",
    "#D9B01C",
    "#F0FAF5",
]

STATS_PASSWORD = env("STATS_PASSWORD", default="")

BASICAUTH_USERS = {"stats": STATS_PASSWORD}
BASICAUTH_REALM = "Knowledge Commons User Stats"

ROR_TIMEOUT = 10
ZENODO_TIMEOUT = 10

ROR_THRESHOLD = 0.6

EXCLUDE_STATS_EMAILS = ["gmail.com", "yahoo.com", "hotmail.com"]

CILOGON_CLIENT_ID = env("CILOGON_CLIENT_ID", default="")
CILOGON_CLIENT_SECRET = env("CILOGON_CLIENT_SECRET", default="")


OIDC_CALLBACK = "cilogon/callback/"

STATIC_API_BEARER = env("STATIC_API_BEARER", default="")

WP_MEDIA_ROOT = env("WP_MEDIA_ROOT", default="")
WP_MEDIA_URL = env("WP_MEDIA_URL", default="")

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 50,
}

ALLOWED_CILOGON_FORWARDING_DOMAINS = env.list(
    "ALLOWED_CILOGON_FORWARDING_DOMAINS",
    default=[
        "hcommons.org",
        "msu.edu",
        "localhost",
        "lndo.site",
        "hcommons-staging.org",
        "hcommons-dev.org",
    ],
)

CILOGON_DISCOVERY_URL = "https://cilogon.org/.well-known/openid-configuration"
CILOGON_SCOPE = "openid email profile org.cilogon.userinfo offline_access"
CILOGON_REFRESH_TOKEN_TIMEOUT = 300
CILOGON_LOGOUT_URL = "https://cilogon.org/logout"
CILOGON_TOKEN_CLEAROUT_DAYS = 4
CILOGON_APP_LIST = ["Profiles", "Works", "WordPress"]

MLA_API_KEY = env("MLA_API_KEY", default="")
MLA_API_SECRET = env("MLA_API_SECRET", default="")
MLA_CACHE_TIMEOUT = 24 * 60 * 60  # 24 hours
MLA_API_BASE_URL = env("MLA_API_BASE_URL", default="https://api.mla.org/2/")

ARLISNA_API_TOKEN = env("ARLISNA_API_TOKEN", default="")
ARLISNA_CACHE_TIMEOUT = 24 * 60 * 60  # 24 hours
ARLISNA_API_BASE_URL = env(
    "ARLISNA_API_BASE_URL", default="https://www.arlisna.org/api/"
)

UP_API_TOKEN = env("UP_API_TOKEN", default="")
UP_CACHE_TIMEOUT = 24 * 60 * 60  # 24 hours
UP_API_BASE_URL = env("UP_API_BASE_URL", default="https://www.up.org/api/")
UP_CLIENT_ID = env("UP_CLIENT_ID", default="")
UP_CLIENT_SECRET = env("UP_CLIENT_SECRET", default="")
UP_REFRESH_TOKEN = env("UP_REFRESH_TOKEN", default="")

EXTERNAL_SYNC_CLASSES: list[tuple[str, list[str]]] = [
    ("MLA", ["Modern Language Association", "MLA"]),
    ("MSU", ["Michigan State University", "MSU"]),
    ("ARLISNA", ["Art Libraries Society of North America", "ARLISNA"]),
    ("UP", ["Association of American University Presses"]),
]

OPEN_REGISTRATION_NETWORKS = env(
    "OPEN_REGISTRATION_NETWORKS",
    default=[
        (
            "HASTAC",
            "Humanities, Arts, Science, and Technology Alliance and Collaboratory",
        ),
        ("SAH", "Society of Architectural Historians"),
        ("STEMEd+", "STEM Ed+"),
    ],
)

KNOWN_SOCIETY_MAPPINGS = {"stemedplus": "STEMED+"}

LOGOUT_ENDPOINTS = []

WORKS_UPDATE_ENDPOINTS = [
    "https://localhost/" if DEBUG else "https://works.hcommons.org/"
]

WEBHOOK_TOKEN = env("WEBHOOK_TOKEN")
WEBHOOK_URLS = env.list("WEBHOOK_URLS", default=[])

THREAD = threading.local()

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

VERIFICATION_LIMIT_HOURS = env.int(
    "VERIFICATION_LIMIT_HOURS", 48
)  # hours before email verifications expires
SYNC_HOURS = env.int(
    "SYNC_HOURS", 24
)  # hours before syncs are considered stale

CC_SEARCH_URL = env("CC_SEARCH_URL", default="https://search.hcommons.org/v1/")
CC_SEARCH_ADMIN_KEY = env("CC_SEARCH_ADMIN_KEY", default="")
CC_SEARCH_TIMEOUT = env.int("CC_SEARCH_TIMEOUT", default=10)
