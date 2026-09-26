import dj_database_url

from .base import *

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("development-"):
    raise ImproperlyConfigured("Set a strong, unique SECRET_KEY of at least 50 characters.")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set explicit ALLOWED_HOSTS; wildcard hosts are forbidden.")
database_url = os.environ.get("DATABASE_URL", "")
if not database_url.startswith(("postgres://", "postgresql://")):
    raise ImproperlyConfigured("DATABASE_URL must be a PostgreSQL connection URL.")
DATABASES = {
    "default": dj_database_url.parse(
        database_url,
        conn_max_age=600,
        conn_health_checks=True,
    )
}
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# Enable only behind a proxy that overwrites this header and terminates HTTPS.
if os.environ.get("TRUST_PROXY_HTTPS") == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
