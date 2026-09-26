FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY apps ./apps
COPY config ./config
COPY manage.py ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN DJANGO_SETTINGS_MODULE=config.settings.development python manage.py collectstatic --noinput \
    && useradd --create-home appuser \
    && chown appuser /app
ENV DJANGO_SETTINGS_MODULE=config.settings.production
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --access-logfile -"]
