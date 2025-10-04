#!/bin/sh

# Fail fast on syntax errors, but vamos controlar falhas de migração manualmente
set -u

echo "==> Iniciando entrypoint (timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ))"

MAX_RETRIES=${MIGRATION_MAX_RETRIES:-10}
INITIAL_SLEEP=${MIGRATION_INITIAL_SLEEP_SECONDS:-3}
BACKOFF_FACTOR=${MIGRATION_BACKOFF_FACTOR:-1.6}

attempt=1
sleep_time=$INITIAL_SLEEP

echo "==> Aplicando migrations (máx ${MAX_RETRIES} tentativas)"
while true; do
	if python manage.py migrate --noinput; then
		echo "==> Migrações aplicadas com sucesso na tentativa ${attempt}"
		break
	fi

	if [ "$attempt" -ge "$MAX_RETRIES" ]; then
		echo "[ERRO] Falha ao aplicar migrações após ${attempt} tentativas. Abortando." >&2
		exit 1
	fi

	attempt=$((attempt + 1))
	# converte sleep_time para inteiro ou mantem decimal
	printf "==> Migração falhou. Nova tentativa (%d/%d) em %.1f s...\n" "$attempt" "$MAX_RETRIES" "$sleep_time"
	# sleep aceita inteiros; para suportar decimal, usamos awk se disponível
	# fallback para inteiro
	if command -v awk >/dev/null 2>&1; then
		awk -v t="$sleep_time" 'BEGIN { system("sleep " t) }'
	else
		sleep $(printf '%.*f' 0 "$sleep_time")
	fi
	# calcula próximo backoff (limitando em 45s)
	# usamos awk para multiplicar float; se não existir, dobramos com shell inteiro
	if command -v awk >/dev/null 2>&1; then
		sleep_time=$(awk -v t="$sleep_time" -v f="$BACKOFF_FACTOR" 'BEGIN { v=t*f; if (v>45) v=45; printf "%.2f", v }')
	else
		sleep_time=$((sleep_time * 2))
		[ "$sleep_time" -gt 45 ] && sleep_time=45
	fi
done

echo "==> Coletando arquivos estáticos"
python manage.py collectstatic --noinput

# echo "$(date)" > build_time.txt  # opcional: gerar carimbo de build

echo "==> Iniciando Gunicorn (workers=3 timeout=120)"
exec gunicorn -b :$PORT pandora_erp.wsgi:application --log-file - --access-logfile - --workers 3 --timeout 120
