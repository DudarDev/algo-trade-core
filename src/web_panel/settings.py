import os
from pathlib import Path

# ==========================================
# 1. PATH CONFIGURATION (АРХІТЕКТУРА ШЛЯХІВ)
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent         # src/
PROJECT_ROOT = BASE_DIR.parent                            # корінь проєкту

# ==========================================
# 2. SECURITY & CORE SETTINGS (БЕЗПЕКА)
# ==========================================
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-update-me-in-production')
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')
CSRF_TRUSTED_ORIGINS = ['https://*.cloudshell.dev']

# ==========================================
# 3. APPLICATIONS (ДОДАТКИ)
# ==========================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # наші додатки
    'bot_monitor',
    'shared',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # --- Whitenoise: роздача статики прямо з Gunicorn ---
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'web_panel.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'web_panel.wsgi.application'

# ==========================================
# 4. DATABASE (ІНФРАСТРУКТУРА ДАНИХ)
# ==========================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': PROJECT_ROOT / 'data_storage' / 'bot_data.db',
    }
}

# ==========================================
# 5. PASSWORD VALIDATION
# ==========================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==========================================
# 6. INTERNATIONALIZATION
# ==========================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ==========================================
# 7. STATIC FILES (Whitenoise)
# ==========================================
STATIC_URL = '/static/'
# Папка, куди Django збиратиме статику (collectstatic)
STATIC_ROOT = PROJECT_ROOT / 'staticfiles'

# Whitenoise storage для стиснення та кешування (manifests)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================
# 8. LOGGING (ОБРОБКА ПОМИЛОК)
# ==========================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '%(asctime)s %(levelname)s [%(name)s:%(lineno)s] %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}