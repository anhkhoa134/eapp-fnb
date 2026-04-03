from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR / "Project"

env = environ.Env()
_env_file = PROJECT_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file), override=True)
else:
    print(f"[settings] WARNING: .env file not found at {_env_file}")

# ─── ENVIRONMENT ────────────────────────────────────────────────────────────
ENVIRONMENT = env("ENVIRONMENT", default="prod").strip().lower()
if ENVIRONMENT not in {"dev", "prod"}:
    ENVIRONMENT = "prod"

DEBUG = env.bool("DEBUG", default=(ENVIRONMENT == "dev"))
print(f"[settings] ENVIRONMENT={ENVIRONMENT}  DEBUG={DEBUG}")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-this-secret-key")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Custom admin URL (bảo mật: không dùng /admin/ mặc định)
REAL_ADMIN_PATH = env("REAL_ADMIN_PATH", default="admin/").strip("/")
REAL_ADMIN_PATH = f"{REAL_ADMIN_PATH}/"

# ─── APPS ────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "daphne",
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "channels",
    "App_Core",
    "App_Accounts",
    "App_PM",
    "App_UI",
]

JAZZMIN_SETTINGS = {
    "site_title": "eApp PM Admin",
    "site_header": "eApp PM",
    "site_brand": "eApp PM",
    "welcome_sign": "Quản trị eApp PM",
    "copyright": "eApp PM",
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "App_Accounts.User": "fas fa-user",
        "App_Accounts.TenantMembership": "fas fa-user-shield",
        "App_Accounts.SubscriptionPlan": "fas fa-tags",
        "App_Accounts.UserSubscription": "fas fa-id-card",
        "App_Core.Tenant": "fas fa-building",
        "App_PM.PMProject": "fas fa-diagram-project",
        "App_PM.PMTask": "fas fa-list-check",
    },
    "order_with_respect_to": [
        "auth",
        "App_Accounts",
        "App_Core",
        "App_PM",
        "App_UI",
    ],
    "topmenu_links": [
        {"name": "Dashboard", "url": "pm:dashboard", "permissions": ["App_PM.view_pmproject"]},
        {"model": "App_Accounts.User"},
        {"model": "App_Accounts.UserSubscription"},
    ],
    "show_ui_builder": False,
}

# ─── MIDDLEWARE ──────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "App_Core.middleware.UserLanguageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "App_Core.middleware.CurrentTenantMiddleware",
    "App_Core.middleware.NotFoundRedirectMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "Project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "App_Core.context_processors.tenant_context",
            ],
        },
    },
]

WSGI_APPLICATION = "Project.wsgi.application"

# ─── DATABASE ────────────────────────────────────────────────────────────────
if ENVIRONMENT == "dev":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    postgres_db = env("POSTGRES_DB", default="eapp_pm")
    postgres_user = env("POSTGRES_USER", default="postgres")
    postgres_password = env("POSTGRES_PASSWORD", default="postgres")
    postgres_host = env("POSTGRES_HOST", default="127.0.0.1")
    postgres_port = env("POSTGRES_PORT", default="5432")
    _default_db_url = (
        f"postgres://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
    )
    DATABASES = {
        "default": env.db("DATABASE_URL", default=_default_db_url)
    }
    if DATABASES["default"].get("ENGINE") != "django.db.backends.postgresql":
        raise ImproperlyConfigured(
            "ENVIRONMENT=prod bắt buộc dùng PostgreSQL (DATABASE_URL phải là postgres://...)."
        )

# ─── AUTH ────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "App_Accounts.User"

AUTHENTICATION_BACKENDS = [
    "App_Accounts.backends.EmailOrUsernameBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "pm:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

SITE_ID = 1

# allauth account config
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True

# allauth socialaccount config (credentials from SocialApp in DB)
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_ADAPTER = "App_Accounts.adapters.EappSocialAccountAdapter"
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"prompt": "select_account"},
    }
}

# ─── LOCALISATION ────────────────────────────────────────────────────────────
LANGUAGE_CODE = "vi"
LANGUAGES = [
    ("vi", _("Tiếng Việt")),
    ("en", _("English")),
]
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# ─── STATIC / MEDIA ──────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── SECURITY ────────────────────────────────────────────────────────────────
# Always-on (safe for both dev & prod)
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

if ENVIRONMENT == "prod":
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# ─── LOGGING ─────────────────────────────────────────────────────────────────
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        },
        "simple": {
            "format": "%(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "recent_error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "recent-errors.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 1,
            "encoding": "utf-8",
            "level": "ERROR",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "recent_error_file"],
        "level": env("LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["recent_error_file"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# ─── CHANNELS / WEBSOCKET ─────────────────────────────────────────────────────
ASGI_APPLICATION = "Project.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://127.0.0.1:6379")],
        },
    }
}
