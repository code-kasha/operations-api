#!/bin/sh
# Hosted demo only: migrate, replace all data with fresh fictional sample data, then serve.
# reset_demo refuses to run unless DEMO_UNTIL is set. See docs/deployment.md.
set -eu
: "${DEMO_PASSWORD:?Set DEMO_PASSWORD for the fictional demo accounts.}"
python manage.py migrate --noinput
python manage.py reset_demo --password "$DEMO_PASSWORD"
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --access-logfile -
