import os
from pathlib import Path

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

DEBUG = env('DEBUG', default=True, cast=bool)
SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me')
ALLOWED_HOSTS = env('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost'], cast=list)
CSRF_TRUSTED_ORIGINS = env('CSRF_TRUSTED_ORIGINS', default=[], cast=list)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
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

DB_ENGINE = env('DB_ENGINE', default='sqlite').strip().lower()
if DB_ENGINE in {'postgres', 'postgresql'}:
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
