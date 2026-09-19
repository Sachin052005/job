"""
Django settings for the NammaCareer job portal project.
"""

from pathlib import Path
import os

from dotenv import load_dotenv


# ============================================================
# BASE DIRECTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE, override=True)


def env_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


# ============================================================
# SECURITY
# ============================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-8p&!82e@^8qh7x7b(q_exj7&*iuken!gy(3xwoy2zbzd4jbek+",
)

DEBUG = env_bool("DEBUG", False)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost",
    ).split(",")
    if host.strip()
]


# ============================================================
# APPLICATION DEFINITION
# ============================================================

INSTALLED_APPS = [
    # ========================================================
    # Django Jazzmin
    # ========================================================
    "jazzmin",

    # ========================================================
    # Django default applications
    # ========================================================
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # ========================================================
    # Project applications
    # ========================================================
    "core",
    "accounts",
    "companies",
    "jobs",
    "applications",
    "saved_jobs",
    "dashboard",
]


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ============================================================
# URL CONFIGURATION
# ============================================================

ROOT_URLCONF = "config.urls"


# ============================================================
# TEMPLATES
# ============================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",

                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ============================================================
# WSGI
# ============================================================

WSGI_APPLICATION = "config.wsgi.application"


# ============================================================
# DATABASE
# ============================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",

        "NAME": os.getenv(
            "DB_NAME",
            "job",
        ),

        "USER": os.getenv(
            "DB_USER",
            "root",
        ),

        "PASSWORD": os.getenv(
            "DB_PASSWORD",
            "",
        ),

        "HOST": os.getenv(
            "DB_HOST",
            "127.0.0.1",
        ),

        "PORT": os.getenv(
            "DB_PORT",
            "3306",
        ),

        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}


# ============================================================
# DEFAULT AUTO FIELD
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ============================================================
# PASSWORD VALIDATION
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },

    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),

        "OPTIONS": {
            "min_length": 8,
        },
    },

    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },

    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ============================================================
# INTERNATIONALIZATION
# ============================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# ============================================================
# STATIC FILES
# ============================================================

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"


# ============================================================
# MEDIA FILES
# ============================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# ============================================================
# FILE UPLOAD LIMITS
# ============================================================

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024


# ============================================================
# EMAIL
# ============================================================

EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
)

DEFAULT_FROM_EMAIL = (
    "NammaCareer <no-reply@nammacareer.local>"
)


# ============================================================
# AUTHENTICATION
# ============================================================

LOGIN_URL = "accounts:login"

LOGIN_REDIRECT_URL = "dashboard:home"

LOGOUT_REDIRECT_URL = "home"


# ============================================================
# SECURITY SETTINGS
# ============================================================

SESSION_COOKIE_HTTPONLY = True

CSRF_COOKIE_HTTPONLY = False

X_FRAME_OPTIONS = "DENY"

SECURE_CONTENT_TYPE_NOSNIFF = True


# ============================================================
# JAZZMIN ADMIN CONFIGURATION
# ============================================================

JAZZMIN_SETTINGS = {
    # --------------------------------------------------------
    # Admin login logo
    # --------------------------------------------------------

    "login_logo": "images/logo.png",

    

    # --------------------------------------------------------
    # Admin sidebar/header logo
    # --------------------------------------------------------

    "site_logo": "images/logo.png",

    # --------------------------------------------------------
    # Admin branding
    # --------------------------------------------------------

    "site_title": "NammaCareer Admin",

    "site_header": "NammaCareer",

    "site_brand": "NammaCareer",

    # --------------------------------------------------------
    # Welcome message
    # --------------------------------------------------------

    "welcome_sign": "Welcome to NammaCareer Administration",

    # --------------------------------------------------------
    # Copyright
    # --------------------------------------------------------

    "copyright": "NammaCareer",

    # --------------------------------------------------------
    # Sidebar
    # --------------------------------------------------------

    "navigation_expanded": True,

    "show_sidebar": True,

    # --------------------------------------------------------
    # Related object modal
    # --------------------------------------------------------

    "related_modal_active": True,

    # --------------------------------------------------------
    # Icons
    # --------------------------------------------------------

    "default_icon_parents": "fas fa-folder",

    "default_icon_children": "fas fa-circle",

    "icons": {
        "auth": "fas fa-users",
    },

    # --------------------------------------------------------
    # Custom CSS
    # --------------------------------------------------------

    "custom_css": "css/admin-custom.css",
}


# ============================================================
# JAZZMIN UI TWEAKS
# ============================================================

JAZZMIN_UI_TWEAKS = {
    # --------------------------------------------------------
    # Theme
    # --------------------------------------------------------

    "theme": "default",

    "dark_mode_theme": None,

    # --------------------------------------------------------
    # Brand
    # --------------------------------------------------------

    "brand_colour": "success",

    "accent": "success",

    # --------------------------------------------------------
    # Sidebar
    # --------------------------------------------------------

    "navbar": "navbar-dark",

    "sidebar": "sidebar-dark-success",

    "sidebar_nav_small_text": False,

    "sidebar_disable_expand": False,

    "sidebar_nav_child_indent": True,

    "sidebar_nav_compact_style": False,

    "sidebar_nav_legacy_style": False,

    "sidebar_nav_flat_style": False,

    # --------------------------------------------------------
    # Navbar
    # --------------------------------------------------------

    "navbar_small_text": False,

    "navbar_fixed": True,

    "navbar_border": True,

    # --------------------------------------------------------
    # Footer
    # --------------------------------------------------------

    "footer_fixed": False,

    # --------------------------------------------------------
    # Body
    # --------------------------------------------------------

    "body_small_text": False,

    # --------------------------------------------------------
    # Buttons
    # --------------------------------------------------------

    "button_classes": {
        "primary": "btn-success",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },

    # --------------------------------------------------------
    # Form styling
    # --------------------------------------------------------

    "actions_sticky_top": True,
}