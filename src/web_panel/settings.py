import os
from pathlib import Path

# ==========================================
# 1. PATH CONFIGURATION (АРХІТЕКТУРА ШЛЯХІВ)
# ==========================================
# BASE_DIR вказує на папку src/
BASE_DIR = Path(__file__).resolve().parent.parent

# PROJECT_ROOT вказує на корінь проєкту (algo-trade-core)
PROJECT_ROOT = BASE_DIR.parent 

# ==========================================
# 2. SECURITY & CORE SETTINGS (БЕЗПЕКА)
# ==========================================
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-update-me-in-production')

# Суворий підхід: в Production DEBUG завжди False, якщо явно не вказано інше
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

# У Production тут мають бути конкретні домени (наприклад, ['my-bot.com', '13.50.111.158'])
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
    
    # --- НАШІ ДОДАТКИ ---
    'bot_monitor', # Додаток для UI та дзеркальних моделей
    'shared',      # Модуль спільних даних бази
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
        # База лежить у спільному томі Docker
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
# 7. STATIC FILES (Nginx Integration)
# ==========================================
STATIC_URL = '/static/'
# Папка, куди Django збиратиме статику для роздачі через Nginx
STATIC_ROOT = PROJECT_ROOT / 'staticfiles'

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