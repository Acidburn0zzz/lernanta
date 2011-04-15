from settings import *

# Useful settings for running a local instance of batucada.

DEBUG = True
TEMPLATE_DEBUG = DEBUG


# Include at least one admin who will receive the reports of abuse.
ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)
MANAGERS = ADMINS


DATABASES = {

    'default': {
        'NAME': 'lernanta',
        'ENGINE': 'django.db.backends.mysql',
        'USER': 'lernanta',
        'PASSWORD': '',
        'HOST': '', # An empty string means localhost.
        'PORT': '', # An empty string means the default port.
        'OPTIONS': {'init_command': 'SET storage_engine=InnoDB'},
    },

    # Comment the following lines to disable drupal user support.
    'drupal_users': {
        'NAME': 'drupal_user_data',
        'TEST_NAME': 'drupal_user_data',
        'ENGINE': 'django.db.backends.mysql',
        'USER': 'drupal_db_user',
        'PASSWORD': '',
        'HOST': '', # An empty string means localhost.
        'PORT': '', # An empty string means the default port.
    }

}

TIME_ZONE = 'America/Toronto'

DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
}

INSTALLED_APPS += (
    'debug_toolbar',
    'django_nose',
)

MIDDLEWARE_CLASSES += (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)
INTERNAL_IPS = ('127.0.0.1',)

# Sign up for an API key at https://www.google.com/recaptcha/admin/create
RECAPTCHA_PUBLIC_KEY = ''
RECAPTCHA_PRIVATE_KEY = ''
RECAPTCHA_URL = ('https://api-secure.recaptcha.net/challenge?k=%s' %
                 RECAPTCHA_PUBLIC_KEY)

# Use dummy caching for development.
CACHE_BACKEND = 'dummy://'
CACHE_PREFIX = 'batucada'
CACHE_COUNT_TIMEOUT = 60

# Execute celery tasks locally, so you don't have to be running an MQ
CELERY_ALWAYS_EAGER = True

# Path to ffmpeg. This will have to be installed to create video thumbnails
FFMPEG_PATH = '/usr/bin/ffmpeg'

# Set to True at production before upgrading lernanta.
# Remember to login as admin before activating maintenance mode.
MAINTENANCE_MODE = False

# Where the default image for sending to Gravatar
DEFAULT_PROFILE_IMAGE = 'http%3A%2F%2Fnew.p2pu.org%2Fmedia%2Fimages%2Fmember-missing.png'
