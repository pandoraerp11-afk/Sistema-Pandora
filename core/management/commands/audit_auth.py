"""Comando de gerenciamento para auditar e gerenciar contadores de negação de acesso a módulos."""

from __future__ import annotations

import contextlib
import logging
import pickle
from typing import TYPE_CHECKING, Any

from django.core.cache import cache
from django.core.management.base import BaseCommand

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None

if TYPE_CHECKING:
    from argparse import ArgumentParser

    from redis import Redis as RedisClient

logger = logging.getLogger(__name__)

CACHE_KEY_PATTERN = "module_deny_count:*"
MIN_TUPLE_LENGTH = 2
REDIS_SCAN_COUNT = 200


class Command(BaseCommand):
    """Audita e gerencia contadores de negação de acesso a módulos armazenados no cache."""

    help = "Audita contadores de negação de módulos (module_deny_count:*) e exibe top N (cache ou Redis)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Adiciona argumentos ao comando."""
        parser.add_argument("--limit", type=int, default=20, help="Limite de linhas exibidas")
        parser.add_argument("--redis-url", type=str, help="URL Redis direta (override)")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Zera todos os contadores module_deny_count:* encontrados",
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401
        """Executa o comando de auditoria."""
        limit = options["limit"]
        items: list[tuple[str, int]] = []

        # Tenta diferentes estratégias para obter as chaves do cache
        if hasattr(cache, "iter_keys"):
            items = self._get_keys_from_iter_keys(CACHE_KEY_PATTERN)
        elif redis and (options.get("redis_url") or cache.__class__.__name__.lower().startswith("rediscache")):
            items = self._get_keys_from_redis_scan(CACHE_KEY_PATTERN, options.get("redis_url"))
        elif hasattr(cache, "_cache"):
            items = self._get_keys_from_locmem(CACHE_KEY_PATTERN)
        else:
            items = self._get_keys_from_dict_scan(CACHE_KEY_PATTERN)

        if not items:
            # Mensagem esperada pelos testes
            self.stdout.write("Nenhum contador encontrado")
            return

        if options.get("reset"):
            self._reset_counters(items)
            self.stdout.write(self.style.SUCCESS(f"{len(items)} contadores resetados."))
        else:
            items.sort(key=lambda x: x[1], reverse=True)
            self.stdout.write(self.style.SUCCESS(f"Exibindo top {limit} de {len(items)} contadores:"))
            for k, v in items[:limit]:
                self.stdout.write(f"{k} => {v}")

    def _get_keys_from_iter_keys(self, pattern: str) -> list[tuple[str, int]]:
        """Obtém chaves usando o método `iter_keys` do cache."""
        items = []
        try:
            for k in cache.iter_keys(pattern):
                try:
                    val = cache.get(k)
                    if val is not None:
                        items.append((k, int(val)))
                except (ValueError, TypeError):
                    logger.warning("Não foi possível converter o valor da chave '%s' para inteiro.", k)
                    continue
        except (AttributeError, TypeError, ValueError) as e:
            self.stdout.write(self.style.ERROR(f"Erro ao iterar chaves do cache: {e}"))
        return items

    def _get_keys_from_redis_scan(self, pattern: str, redis_url: str | None) -> list[tuple[str, int]]:
        """Obtém chaves de um backend Redis usando SCAN."""
        if not redis:
            return []
        items = []
        try:
            r = self._get_redis_client(redis_url)
            if not r:
                self.stdout.write(self.style.WARNING("Cliente Redis não pôde ser inicializado."))
                return []

            for key_bytes in r.scan_iter(match=pattern, count=REDIS_SCAN_COUNT):
                try:
                    raw_val = r.get(key_bytes)
                    if raw_val is None:
                        continue
                    key = key_bytes.decode()
                    val = int(raw_val)  # type: ignore[arg-type]
                    items.append((key, val))
                except (ValueError, TypeError):
                    logger.warning("Valor inválido para a chave Redis '%s'.", key_bytes)
                except redis.RedisError:
                    logger.exception("Erro no Redis ao processar a chave '%s'", key_bytes)
        except redis.RedisError as e:
            self.stdout.write(self.style.ERROR(f"Falha na conexão ou comando Redis: {e}"))
        return items

    def _get_redis_client(self, redis_url: str | None) -> RedisClient | None:
        """Obtém um cliente Redis, seja da URL ou do cache do Django."""
        if not redis:
            return None
        if redis_url:
            return redis.from_url(redis_url)

        base_client = getattr(cache, "client", None)
        if base_client and hasattr(base_client, "get_client"):
            return base_client.get_client(write=True)
        return None

    def _get_keys_from_locmem(self, pattern: str) -> list[tuple[str, int]]:
        """Heurística para obter chaves do LocMemCache."""
        items = {}
        try:
            internal_cache = cache._cache  # noqa: SLF001
            for key, raw_value in list(internal_cache.items()):
                if not (isinstance(key, str) and pattern.strip("*") in key):
                    continue

                value = self._decode_cache_value(raw_value)
                if value is not None:
                    try:
                        items[key] = int(value)
                    except (ValueError, TypeError):
                        continue
        except (AttributeError, TypeError) as e:
            self.stdout.write(self.style.WARNING(f"Falha ao inspecionar LocMemCache: {e}"))
        return list(items.items())

    def _get_keys_from_dict_scan(self, pattern: str) -> list[tuple[str, int]]:
        """Heurística de última instância para encontrar chaves em caches baseados em dict."""
        items = {}
        try:
            for attr_name in dir(cache):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(cache, attr_name, None)
                if not isinstance(attr, dict):
                    continue

                for key, raw_value in list(attr.items()):
                    if not (isinstance(key, str) and pattern.strip("*") in key):
                        continue

                    value = self._decode_cache_value(raw_value)
                    if value is not None:
                        try:
                            items[key] = int(value)
                        except (ValueError, TypeError):
                            continue
        except (AttributeError, TypeError) as e:
            self.stdout.write(self.style.WARNING(f"Falha ao varrer atributos do cache: {e}"))
        return list(items.items())

    def _decode_cache_value(self, raw_value: Any) -> Any:  # noqa: ANN401
        """Decodifica um valor do cache, tratando tuplas e pickle."""
        value = raw_value
        if isinstance(value, tuple) and len(value) >= MIN_TUPLE_LENGTH:
            value = value[1]
        if isinstance(value, bytes):
            with contextlib.suppress(pickle.UnpicklingError, TypeError):
                # S301: O uso de pickle é um risco se os dados não forem confiáveis.
                # Neste comando de admin, o risco é considerado aceitável.
                value = pickle.loads(value)  # noqa: S301
        return value

    def _reset_counters(self, items: list[tuple[str, int]]) -> None:
        """Reseta os contadores de negação no cache."""
        # Tentar caminho otimizado via Redis se possível
        used_redis = False
        if redis:
            try:
                r = self._get_redis_client(None)
                if r is not None:
                    used_redis = True
                    pipe = r.pipeline()
                    for key, _ in items:
                        pipe.delete(key)
                    pipe.execute()
            except Exception as e:  # noqa: BLE001
                used_redis = False
                self.stdout.write(self.style.WARNING(f"Falha ao resetar via Redis: {e}"))

        if not used_redis:
            for key, _ in items:
                try:
                    # Alguns backends (LocMem) armazenam internamente com prefixo (ex.: ":1:")
                    cache.delete(key)
                    # Tentar também a variante "normalizada" sem prefixo interno
                    if "module_deny_count:" in key:
                        idx = key.find("module_deny_count:")
                        original_key = key[idx:]
                        if original_key != key:
                            cache.delete(original_key)
                except (AttributeError, TypeError, ValueError) as e:
                    self.stdout.write(self.style.WARNING(f"Não foi possível deletar a chave '{key}': {e}"))
