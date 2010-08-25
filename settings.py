# -*- coding: utf-8 -*-
# Django settings for batucada project.

import os

# Make filepaths relative to settings.
ROOT = os.path.dirname(os.path.abspath(__file__))
path = lambda *a: os.path.join(ROOT, *a)

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'batucada.db',
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Toronto'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

SUPPORTED_NONLOCALES = ('media', '.well-known', 'accountmanager')

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = path('media')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/admin-media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'std3j$ropgs216z1aa#8+p3a2w2q06mns_%2vfx_#$$i!+6o+x'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'l10n.middleware.LocaleURLRewriter',
    'accountmanager.middleware.StatusHeader',
)

ROOT_URLCONF = 'batucada.urls'

TEMPLATE_DIRS = (
    path('templates'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.admin',
    'django_openid_auth',
    'wellknown',
    'users',
    'profiles',
    'l10n',
    'dashboard',
    'relationships',
    'accountmanager',
    'activity',
)

WELLKNOWN_HOSTMETA_HOSTS = ('localhost:8000',)
MOZILLA_AMCD_HREF = '/meta/amcd.json'

# Auth settings
LOGIN_URL = '/'
LOGIN_REDIRECT_URL = '/'

ACCOUNT_ACTIVATION_DAYS = 7

AUTHENTICATION_BACKENDS = (
    'users.auth.CustomOpenIDBackend',
    'django.contrib.auth.backends.ModelBackend',
)

AUTH_PROFILE_MODULE = 'profiles.Profile'

MAX_IMAGE_SIZE = 1024 * 700

AMCD_RESOLVER_FUNCTION = 'l10n.urlresolvers.reverse'
AMCD_CONFIG = {
    'connect': {
        'method': 'POST',
        'path_view': 'users.views.login',
        'params': {
            'username': 'username',
            'password': 'password'
        }
    },
    'disconnect': {
        'method': 'GET',
        'path_view': 'users.views.logout'
    },
    'register': {
        'method': 'POST',
        'path_view': 'users.views.register',
        'type': 'email',
        'params': {
            'id': 'email',
            'secret': 'password'
        }
    }
}
