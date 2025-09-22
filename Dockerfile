########## STAGE 1: builder ##########
FROM python:3.13-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 POETRY_VIRTUALENVS_CREATE=false
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libffi-dev \
    libpango-1.0-0 libpangoft2-1.0-0 libpango1.0-dev \
    libjpeg62-turbo-dev zlib1g-dev libwebp-dev \
    libmagic1 file ghostscript ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .
RUN useradd -m appuser && chown -R appuser /app

########## STAGE 2: runtime ##########
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev libpango-1.0-0 libpangoft2-1.0-0 \
    libjpeg62-turbo-dev zlib1g-dev libwebp-dev libmagic1 ghostscript ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Entrypoint: migrações e estáticos antes de iniciar
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && chown appuser:appuser /app/entrypoint.sh

USER appuser

EXPOSE 8000
ENV GUNICORN_WORKERS=3 GUNICORN_TIMEOUT=90
CMD ["/app/entrypoint.sh"]

# Target de desenvolvimento (executar com --target dev)
FROM builder AS dev
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
