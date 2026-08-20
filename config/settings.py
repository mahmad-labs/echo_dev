from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

ENVIRONMENT = os.getenv('DJANGO_ENV', 'development').strip().lower()
DEBUG = os.getenv('DJANGO_DEBUG', 'true' if ENVIRONMENT == 'development' else 'false').lower() == 'true'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') or ('echo-local-development-key' if DEBUG else '')
if not SECRET_KEY:
    raise RuntimeError('DJANGO_SECRET_KEY is required outside development.')

ALLOWED_HOSTS = [x.strip() for x in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if x.strip()]
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if x.strip()]

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'corsheaders', 'rest_framework', 'rest_framework_simplejwt.token_blacklist',
    'django_filters', 'drf_spectacular',
    'echo.apps.authentication.apps.AuthenticationConfig',
    'echo.apps.core.apps.CoreConfig',
    'echo.apps.dashboard.apps.DashboardConfig',
    'echo.apps.chat.apps.ChatConfig',
    'echo.apps.ai_engine.apps.AiEngineConfig',
    'echo.apps.memory.apps.MemoryConfig',
    'echo.apps.vector_database.apps.VectorDatabaseConfig',
    'echo.apps.knowledge.apps.KnowledgeConfig',
    'echo.apps.documents.apps.DocumentsConfig',
    'echo.apps.internet.apps.InternetConfig',
    'echo.apps.code_assistant.apps.CodeAssistantConfig',
    'echo.apps.planner.apps.PlannerConfig',
    'echo.apps.agent_manager.apps.AgentManagerConfig',
    'echo.apps.workflow_engine.apps.WorkflowEngineConfig',
    'echo.apps.tool_manager.apps.ToolManagerConfig',
    'echo.apps.tasks.apps.TasksConfig',
    'echo.apps.calendar.apps.CalendarConfig',
    'echo.apps.email.apps.EmailConfig',
    'echo.apps.notifications.apps.NotificationsConfig',
    'echo.apps.api.apps.ApiConfig',
    'echo.apps.analytics.apps.AnalyticsConfig',
    'echo.apps.settings.apps.SettingsConfig',
    'echo.apps.voice.apps.VoiceConfig',
    'echo.apps.projects.apps.ProjectsConfig',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'echo.common.middleware.CorrelationIdMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'echo.common.middleware.RequestAuditMiddleware',
]

ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages', 'echo.common.context_processors.platform_context',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'


def database_config(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme in {'sqlite', 'sqlite3'}:
        path = unquote(parsed.path or '')
        if path in {'/:memory:', ':memory:'}:
            name = ':memory:'
        elif url.startswith(('sqlite:////', 'sqlite3:////')):
            name = Path('/') / path.lstrip('/')
        else:
            name = BASE_DIR / (path.lstrip('/') or 'db.sqlite3')
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': name}
    if parsed.scheme in {'postgres', 'postgresql'}:
        options = dict(parse_qsl(parsed.query))
        return {
            'ENGINE': 'django.db.backends.postgresql', 'NAME': parsed.path.lstrip('/'),
            'USER': unquote(parsed.username or ''), 'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname or 'localhost', 'PORT': parsed.port or 5432,
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '60')),
            'OPTIONS': {'sslmode': options.get('sslmode', os.getenv('DB_SSLMODE', 'prefer'))},
        }
    raise RuntimeError(f'Unsupported DATABASE_URL scheme: {parsed.scheme}')

DATABASES = {'default': database_config(os.getenv('DATABASE_URL', 'sqlite:///db.sqlite3'))}
AUTH_USER_MODEL = 'authentication.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
PASSWORD_HASHERS = ['django.contrib.auth.hashers.Argon2PasswordHasher', 'django.contrib.auth.hashers.PBKDF2PasswordHasher']

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('DEFAULT_TIMEZONE', 'UTC')
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'false').lower() == 'true'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', str(25 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE

CORS_ALLOWED_ORIGINS = [x.strip() for x in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if x.strip()]
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'echo.apps.authentication.api_authentication.APITokenAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_PAGINATION_CLASS': 'echo.common.pagination.StandardPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter', 'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'echo.common.exceptions.api_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': ('rest_framework.throttling.AnonRateThrottle', 'rest_framework.throttling.UserRateThrottle'),
    'DEFAULT_THROTTLE_RATES': {'anon': '30/min', 'user': '600/hour', 'login': '10/min'},
}
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_MINUTES', '15'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_DAYS', '7'))),
    'ROTATE_REFRESH_TOKENS': True, 'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True, 'AUTH_HEADER_TYPES': ('Bearer',),
}
SPECTACULAR_SETTINGS = {
    'TITLE': 'Echo Enterprise API', 'DESCRIPTION': 'Integrated API for the Echo enterprise platform.',
    'VERSION': '1.0.0', 'SERVE_INCLUDE_SCHEMA': False,
}

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'false').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'echo@localhost')

REDIS_URL = os.getenv('REDIS_URL', '')
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'echo-local'}}
if REDIS_URL:
    CACHES['default'] = {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL}
CELERY_BROKER_URL = REDIS_URL or 'memory://'
CELERY_RESULT_BACKEND = REDIS_URL or 'cache+memory://'
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'true').lower() == 'true'
CELERY_TASK_EAGER_PROPAGATES = True

AI_PROVIDER_BASE_URL = os.getenv('AI_PROVIDER_BASE_URL', '')
AI_PROVIDER_API_KEY = os.getenv('AI_PROVIDER_API_KEY', '')
AI_PROVIDER_MODEL = os.getenv('AI_PROVIDER_MODEL', '')
AI_VISION_MODEL = os.getenv('AI_VISION_MODEL', '')

# Echo general-purpose browser/computer-use runtime. Selenium Manager resolves
# browser drivers automatically; a supported local browser must be installed.
ECHO_BROWSER_ENGINE = os.getenv('ECHO_BROWSER_ENGINE', 'chrome')
ECHO_BROWSER_BINARY = os.getenv('ECHO_BROWSER_BINARY', '')
ECHO_BROWSER_REMOTE_URL = os.getenv('ECHO_BROWSER_REMOTE_URL', '')
ECHO_BROWSER_HEADLESS = os.getenv('ECHO_BROWSER_HEADLESS', 'false').lower() == 'true'
ECHO_BROWSER_ALLOW_LOCALHOST = os.getenv('ECHO_BROWSER_ALLOW_LOCALHOST', 'false').lower() == 'true'
ECHO_BROWSER_ALLOW_PRIVATE_NETWORKS = os.getenv('ECHO_BROWSER_ALLOW_PRIVATE_NETWORKS', 'false').lower() == 'true'
ECHO_BROWSER_PAGELOAD_TIMEOUT = int(os.getenv('ECHO_BROWSER_PAGELOAD_TIMEOUT', '30'))
ECHO_BROWSER_SCRIPT_TIMEOUT = int(os.getenv('ECHO_BROWSER_SCRIPT_TIMEOUT', '20'))
ECHO_BROWSER_MAX_WAIT = int(os.getenv('ECHO_BROWSER_MAX_WAIT', '20'))
ECHO_COMPUTER_USE_MAX_REPLANS = int(os.getenv('ECHO_COMPUTER_USE_MAX_REPLANS', '2'))
ECHO_COMPUTER_USE_MAX_STEPS = int(os.getenv('ECHO_COMPUTER_USE_MAX_STEPS', '30'))
ECHO_COMPUTER_USE_MAX_RUNTIME_SECONDS = int(os.getenv('ECHO_COMPUTER_USE_MAX_RUNTIME_SECONDS', '900'))
ECHO_LOCAL_BACKGROUND_WORKERS = int(os.getenv('ECHO_LOCAL_BACKGROUND_WORKERS', '2'))
ECHO_BROWSER_DOWNLOAD_TIMEOUT = int(os.getenv('ECHO_BROWSER_DOWNLOAD_TIMEOUT', '20'))
ECHO_MEDIA_MAX_VISUAL_SAMPLES = int(os.getenv('ECHO_MEDIA_MAX_VISUAL_SAMPLES', '6'))
ECHO_MEDIA_MAX_AUDIO_SAMPLES = int(os.getenv('ECHO_MEDIA_MAX_AUDIO_SAMPLES', '3'))
ECHO_MEDIA_AUDIO_SAMPLE_SECONDS = float(os.getenv('ECHO_MEDIA_AUDIO_SAMPLE_SECONDS', '6'))
ECHO_MEDIA_STT_PROVIDER = os.getenv('ECHO_MEDIA_STT_PROVIDER', '')
ECHO_MEDIA_MAX_TRANSCRIPT_CHARS = int(os.getenv('ECHO_MEDIA_MAX_TRANSCRIPT_CHARS', '120000'))

# Local/remote desktop Computer Control. OS UI-tree inspection is replaceable via
# a dotted provider class and visual interpretation remains an evidence fallback.
ECHO_COMPUTER_UI_TREE_PROVIDER_CLASS = os.getenv('ECHO_COMPUTER_UI_TREE_PROVIDER_CLASS', '')
ECHO_DESKTOP_ACTION_PAUSE = float(os.getenv('ECHO_DESKTOP_ACTION_PAUSE', '0.08'))
ECHO_DESKTOP_VERIFY_DELAY = float(os.getenv('ECHO_DESKTOP_VERIFY_DELAY', '0.20'))

VOICE_PROVIDER_BASE_URL = os.getenv('VOICE_PROVIDER_BASE_URL', '')
VOICE_PROVIDER_API_KEY = os.getenv('VOICE_PROVIDER_API_KEY', '')
VOICE_MAX_AUDIO_BYTES = int(os.getenv('VOICE_MAX_AUDIO_BYTES', str(25 * 1024 * 1024)))
VOICE_MAX_SYNTHESIS_BYTES = int(os.getenv('VOICE_MAX_SYNTHESIS_BYTES', str(25 * 1024 * 1024)))
VOICE_PROVIDER_TIMEOUT = int(os.getenv('VOICE_PROVIDER_TIMEOUT', '60'))
VOICE_STT_PROVIDER_CLASS = os.getenv('VOICE_STT_PROVIDER_CLASS', '')
VOICE_TTS_PROVIDER_CLASS = os.getenv('VOICE_TTS_PROVIDER_CLASS', '')
VOICE_ACTIVE_SESSION_MINUTES = min(60, max(1, int(os.getenv('VOICE_ACTIVE_SESSION_MINUTES', '60'))))
VOICE_WAKE_WORD_MIN_CONFIDENCE = min(1.0, max(0.0, float(os.getenv('VOICE_WAKE_WORD_MIN_CONFIDENCE', '0.45'))))
VOICE_WAKE_WORD_COOLDOWN_SECONDS = max(0.5, float(os.getenv('VOICE_WAKE_WORD_COOLDOWN_SECONDS', '2.0')))
ECHO_APPLICATION_VERIFY_DELAY = min(5.0, max(0.1, float(os.getenv('ECHO_APPLICATION_VERIFY_DELAY', '0.8'))))
VOICE_SPEAKER_THRESHOLD = min(0.99, max(0.1, float(os.getenv('VOICE_SPEAKER_THRESHOLD', '0.82'))))
VOICE_SPEAKER_MIN_SAMPLES = max(2, int(os.getenv('VOICE_SPEAKER_MIN_SAMPLES', '3')))
VOICE_SPEAKER_MIN_QUALITY = min(1.0, max(0.0, float(os.getenv('VOICE_SPEAKER_MIN_QUALITY', '0.35'))))
VOICE_SPEAKER_PROVIDER_CLASS = os.getenv('VOICE_SPEAKER_PROVIDER_CLASS', '')
DOCUMENT_MAX_EXTRACTED_CHARS = int(os.getenv('DOCUMENT_MAX_EXTRACTED_CHARS', '2000000'))

INTERNET_SEARCH_ENDPOINT = os.getenv('INTERNET_SEARCH_ENDPOINT', '')
INTERNET_SEARCH_API_KEY = os.getenv('INTERNET_SEARCH_API_KEY', '')

LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'json': {'()': 'echo.common.logging.JsonFormatter'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'json'}},
    'root': {'handlers': ['console'], 'level': os.getenv('LOG_LEVEL', 'INFO')},
    'loggers': {'django.request': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False}},
}

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
