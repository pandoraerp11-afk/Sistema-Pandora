#!/usr/bin/env bash
set -euo pipefail

# Coletar estáticos e aplicar migrações
python manage.py collectstatic --noinput
python manage.py migrate --noinput

# Iniciar Gunicorn ASGI (UvicornWorker)
exec gunicorn pandora_erp.asgi:application \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-90}"
