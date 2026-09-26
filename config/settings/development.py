from .base import *

DEBUG = True
SECRET_KEY = "development-only-unsafe-key-never-use-this-key-in-production"
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "[::1]"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
