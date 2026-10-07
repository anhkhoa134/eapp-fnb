#!/bin/sh
set -e

# --skip-checks: system checks import every URL module; code that queries the DB at import time
# (choices=Model.objects...) would crash migrate on the first deploy, before the tables exist.
python manage.py migrate --noinput --skip-checks

# Daphne serves HTTP and WebSocket (/ws/, Channels + Redis) on one port: on VPS 2 this replaces
# gunicorn-eapp-fnb + daphne-eapp-fnb. Static files come from WhiteNoise.
# --proxy-headers: client IP / scheme from Nginx (X-Forwarded-For, X-Forwarded-Proto).
exec daphne -b 0.0.0.0 -p 8000 --proxy-headers Project.asgi:application
