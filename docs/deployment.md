# Deployment foundation

No live deployment or published image is configured yet. This document describes the current container and settings, not a production release.

Build locally with `docker build -t operations-api:local .`. The image defaults to production settings and runs Gunicorn as an unprivileged user. Static admin/Swagger/ReDoc assets are collected at build time and served by WhiteNoise. Migrations are an explicit deployment step, not part of production server startup.

Copy `.env.example` to `.env` and replace the example secret and database credentials before deployment. Python does not load `.env` automatically; export variables in your shell or use Docker's `--env-file .env`.

Required production environment:

| Variable | Value |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` (container default) |
| `SECRET_KEY` | Unique random secret, at least 50 characters; generate with Django's `get_random_secret_key`. |
| `ALLOWED_HOSTS` | Comma-separated hostnames, no wildcard. |
| `DATABASE_URL` | PostgreSQL URL; use `sslmode=require` for Neon. |
| `CSRF_TRUSTED_ORIGINS` | HTTPS origin(s) for admin behind a proxy. |
| `TRUST_PROXY_HTTPS` | `true` only when the trusted proxy overwrites `X-Forwarded-Proto`. |
| `ORGANISATION_NAME` | Single installation's organisation name. |
| `ORGANISATION_SECTOR` | `school`, `clinic`, or `office` (default). Configuration only; modules are planned. |
| `PORT` | HTTP listening port, default 8000. |

```sh
docker run --rm --env-file .env operations-api:local python manage.py check --deploy
docker run --rm --env-file .env operations-api:local python manage.py migrate --noinput
docker run --rm -it --env-file .env operations-api:local python manage.py createsuperuser
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 operations-api:local
```

Production forces HTTPS, secure cookies, and HSTS. Place it behind an HTTPS reverse proxy and configure its forwarded headers before routing traffic. `/health/` checks database connectivity but not migration state. Schedule `python manage.py flushexpiredtokens` daily. Provision backups and proxy rate limiting before public use.

SQLite is intentional for tests and CI. PostgreSQL runtime behavior has not yet been integration-tested. Multi-architecture publication, Render/Neon setup, release checksums, and a demo end date are future release tasks.
