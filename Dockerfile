FROM python:3.13-slim
LABEL org.opencontainers.image.title="operations-api"       org.opencontainers.image.description="Staff operations API for one organisation: staff, attendance, office timesheets, payroll and reports. Django + PostgreSQL. Fictional data only."       org.opencontainers.image.source="https://github.com/code-kasha/operations-api"       org.opencontainers.image.licenses="MIT"
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY apps ./apps
COPY config ./config
COPY manage.py ./
COPY deploy ./deploy
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN DJANGO_SETTINGS_MODULE=config.settings.development python manage.py collectstatic --noinput \
    && useradd --create-home appuser \
    && chown appuser /app
ENV DJANGO_SETTINGS_MODULE=config.settings.production
USER appuser
# Listens on $PORT when a host sets it (Render, most PaaS), otherwise on 8000.
# Migrations are a separate deployment step; the demo uses deploy/demo-start.sh instead.
EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --access-logfile -"]
