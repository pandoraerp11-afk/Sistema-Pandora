"""Comando para inspecionar e/ou resetar métricas simples e contadores de cache.

Objetivos:
- Listar chaves de métricas conhecidas (module_deny_count:*, perm_resolver:*) em backends simples (LocMem, Redis se disponível).
- Exibir valores inteiros.
- Opcional --reset para zerar/remover chaves.
- Foco em debug rápido local/testes – não substitui Prometheus.
"""

from __future__ import annotations

import contextlib

from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Lista ou reseta métricas simples armazenadas em cache (module_deny_count, permission_resolver)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Reseta (remove) as chaves de métricas listadas")
        parser.add_argument("--limit", type=int, default=200, help="Limite de chaves a mostrar (default 200)")
        parser.add_argument("--contains", type=str, default=None, help="Filtro substring opcional")

    def handle(self, *args, **options):
        reset = options["reset"]
        limit = options["limit"]
        contains = options["contains"]

        interesting_prefixes = ["module_deny_count:", "perm_resolver"]
        printed = 0
        listed = []

        # Tentativa específica para Redis (SCAN)
        cache_client = getattr(cache, "client", None)
        tried_scan = False
        if cache_client:
            try:
                client = cache_client.get_client(write=True)
                cursor = 0
                while True:
                    cursor, keys = client.scan(cursor=cursor, match="*", count=500)
                    for k in keys:
                        ks = k.decode() if isinstance(k, bytes) else k
                        if any(p in ks for p in interesting_prefixes):
                            if contains and contains not in ks:
                                continue
                            listed.append(ks)
                    if cursor == 0 or len(listed) >= limit:
                        break
                tried_scan = True
            except Exception:
                pass

        if not tried_scan:
            # Fallback heurístico para LocMemCache / dicionários
            internal = getattr(cache, "_cache", None)
            if isinstance(internal, dict):
                for k in list(internal.keys()):
                    ks = str(k)
                    if any(p in ks for p in interesting_prefixes):
                        # Normalizar para remover possíveis prefixos de versionamento (ex: :1:)
                        ks_norm = ks[3:] if ks.startswith(":1:") else ks
                        if contains and contains not in ks_norm:
                            continue
                        listed.append(ks_norm)
                        if len(listed) >= limit:
                            break

        listed = sorted(set(listed))[:limit]
        if not listed:
            self.stdout.write(self.style.WARNING("Nenhuma métrica encontrada"))
            return

        for key in listed:
            val = cache.get(key)
            self.stdout.write(f"{key}={val}")
            printed += 1
            if reset:
                with contextlib.suppress(Exception):
                    cache.delete(key)
        if reset:
            self.stdout.write(self.style.SUCCESS(f"Reset concluído ({printed} chaves removidas)"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Total exibido: {printed}"))
