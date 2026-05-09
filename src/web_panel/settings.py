from pathlib import Path
import os

# BASE_DIR тепер вказує на папку src/
BASE_DIR = Path(__file__).resolve().parent.parent
# PROJECT_ROOT вказує на корінь проєкту (algo-trade-core)
PROJECT_ROOT = BASE_DIR.parent 

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-update-me')
DEBUG = True
ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = ['https://*.cloudshell.dev']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # --- НАШІ ДОДАТКИ ---
    'bot_monitor', # Додаток для UI та дзеркальних моделей
    'shared',      # ДОДАНО: Реєстрація модуля спільних даних (щоб Django бачив shared/apps.py)
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
        # Прибрали старий шлях до 'app'. APP_DIRS=True сам знайде шаблони у bot_monitor
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        # ВИПРАВЛЕНО: Тепер Django шукає базу в правильній папці нової архітектури
        'NAME': PROJECT_ROOT / 'data_storage' / 'bot_data.db',
    }
}

# ... (все інше нижче, починаючи з AUTH_PASSWORD_VALIDATORS, залишай як було)