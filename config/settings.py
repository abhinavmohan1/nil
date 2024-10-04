import os
from pathlib import Path
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'paolo191#'

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'debug_toolbar',
    'rest_framework',
    'rest_framework.authtoken',
    'dj_rest_auth',
    'django_filters',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'core',
    'bbb_integration.apps.BbbIntegrationConfig',
    'courses',
    'attendance',
    'users.apps.UsersConfig',
    'team_communication',
    'corsheaders',
    'messaging',
    'notifications',
    'leave_management',
]

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb2',
        'USER': 'myuser',
        'PASSWORD': 'mypassword',
        'HOST': 'localhost',
        'PORT': '5432',
        
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
AUTH_USER_MODEL = 'users.User'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1

INTERNAL_IPS = [
    '127.0.0.1',
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
}

REST_AUTH_SERIALIZERS = {
    'TOKEN_SERIALIZER': 'dj_rest_auth.serializers.TokenSerializer',
}

CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

CELERY_BEAT_SCHEDULE = {
    'mark_absent_attendances': {
        'task': 'attendance.tasks.mark_absent_attendances',
        'schedule': crontab(hour=23, minute=59),
    },
    'mark_comp_attendances': {
        'task': 'attendance.tasks.mark_comp_attendances',
        'schedule': crontab(hour=23, minute=59, day_of_week='sat,sun'),
    },
    'create_bbb_rooms': {
        'task': 'bbb_integration.tasks.create_bbb_rooms',
        'schedule': crontab(hour=0, minute=0),
    },
    'delete_expired_recordings': {
        'task': 'bbb_integration.tasks.delete_expired_recordings',
        'schedule': crontab(hour=1, minute=0),
    },
    'sync_bbb_recordings': {
        'task': 'bbb_integration.tasks.sync_bbb_recordings',
        'schedule': crontab(minute='*/30'),
    },
    'update_dashboard_stats': {
        'task': 'core.tasks.update_dashboard_stats',
        'schedule': crontab(minute='*/10'),
    },
    'check_course_holds': {
        'task': 'attendance.tasks.check_course_holds',
        'schedule': crontab(minute='0', hour='0'),  # Run daily at midnight
    },
    'delete_expired_study_materials': {
        'task': 'courses.tasks.delete_expired_study_materials',
        'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
    },
    'check_course_end_dates': {
        'task': 'courses.tasks.check_course_end_dates',
        'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
    },
    'check_and_end_meetings': {
        'task': 'bbb_integration.tasks.check_and_end_meetings',
        'schedule': crontab(minute='*/15'),  # Run every 15 minutes
    },
    'clean_old_leave_history': {
        'task': 'leave_management.tasks.clean_old_leave_history',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2:00 AM
    },
    
    'delete_old_review_history': {
        'task': 'attendance.tasks.delete_old_review_history',
        'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
    },
    
    'delete_old_feedback_history': {
        'task': 'courses.tasks.delete_old_feedback_history',
        'schedule': crontab(hour=0, minute=30),  # Run daily at 00:30
    },
    
    'delete_expired_audits': {
        'task': 'your_app_name.tasks.delete_expired_audits',
        'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
    },

}

CORS_ALLOW_ALL_ORIGINS = False  # Set to True to allow all origins (not recommended for production)

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React default port
    "http://127.0.0.1:3000",
    # Add any other origins (frontend URLs) you want to allow
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# BigBlueButton settings
BBB_URL = 'https://class.nationalinstituteoflanguage.in/bigbluebutton/'
BBB_SECRET = 'tPZpS9HX0DhRAKJemhAebtZ3yVnmQoznti6uBXgWY'