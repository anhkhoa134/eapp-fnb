import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(env_file: Path):
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(key, default=None, cast=str):
    value = os.environ.get(key)
    if value is None:
        return default
    if cast is bool:
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    if cast is int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    if cast is list:
        return [item.strip() for item in value.split(',') if item.strip()]
    return value


_load_env_file(BASE_DIR / 'Project' / '.env')

ENVIRONMENT = env('ENVIRONMENT', default='dev').strip().lower()
if ENVIRONMENT not in {'dev', 'prod'}:
    ENVIRONMENT = 'dev'

DEBUG = env('DEBUG', default=(ENVIRONMENT == 'dev'), cast=bool)
SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me')
ALLOWED_HOSTS = env('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost'], cast=list)
CSRF_TRUSTED_ORIGINS = env('CSRF_TRUSTED_ORIGINS', default=[], cast=list)

REAL_ADMIN_PATH = env('REAL_ADMIN_PATH', default='admin').strip().strip('/')
if not REAL_ADMIN_PATH:
    REAL_ADMIN_PATH = 'admin'
REAL_ADMIN_PATH = f'{REAL_ADMIN_PATH}/'


def env_required(key):
    value = env(key, default='').strip()
    if not value:
        raise ImproperlyConfigured(f'Missing required environment variable: {key}')
    return value

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'daphne',
    'django.contrib.staticfiles',
    'channels',
    'App_Core',
    'App_Accounts',
    'App_Tenant',
    'App_Catalog',
    'App_Sales',
    'App_Quanly',
    'App_Public',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'Project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'App_Core.context_processors.core_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'Project.wsgi.application'
ASGI_APPLICATION = 'Project.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [env('REDIS_URL', default='redis://127.0.0.1:6379')],
        },
    }
}

if ENVIRONMENT == 'prod':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env_required('POSTGRES_DB'),
            'USER': env_required('POSTGRES_USER'),
            'PASSWORD': env_required('POSTGRES_PASSWORD'),
            'HOST': env_required('POSTGRES_HOST'),
            'PORT': env_required('POSTGRES_PORT'),
            'CONN_MAX_AGE': env('POSTGRES_CONN_MAX_AGE', default=60, cast=int),
        }
    }
else:
    use_postgres_in_dev = bool(env('POSTGRES_DB', default='').strip())
    if use_postgres_in_dev:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': env('POSTGRES_DB', default='project_db'),
                'USER': env('POSTGRES_USER', default='postgres'),
                'PASSWORD': env('POSTGRES_PASSWORD', default=''),
                'HOST': env('POSTGRES_HOST', default='127.0.0.1'),
                'PORT': env('POSTGRES_PORT', default='5432'),
                'CONN_MAX_AGE': env('POSTGRES_CONN_MAX_AGE', default=60, cast=int),
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': env('SQLITE_NAME', default=BASE_DIR / 'db.sqlite3'),
            }
        }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'App_Accounts.User'

LOGIN_URL = 'App_Accounts:login'
LOGIN_REDIRECT_URL = 'App_Sales:pos'
LOGOUT_REDIRECT_URL = 'App_Accounts:login'

SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

SECURE_SSL_REDIRECT = env('SECURE_SSL_REDIRECT', default=(ENVIRONMENT == 'prod'), cast=bool)
SECURE_HSTS_SECONDS = env(
    'SECURE_HSTS_SECONDS',
    default=(31536000 if ENVIRONMENT == 'prod' else 0),
    cast=int,
)

if ENVIRONMENT == 'prod':
    if SECRET_KEY == 'django-insecure-change-me':
        raise ImproperlyConfigured('SECRET_KEY must be set in production.')
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured('ALLOWED_HOSTS must be set in production.')

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

LOG_LEVEL = env('LOG_LEVEL', default='INFO').upper()
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        },
        'simple': {
            'format': '%(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'recent_error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'recent-errors.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 1,
            'encoding': 'utf-8',
            'level': 'ERROR',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'recent_error_file'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django.request': {
            'handlers': ['recent_error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
