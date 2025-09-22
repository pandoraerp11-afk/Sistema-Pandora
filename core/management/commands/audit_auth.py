import contextlib

from django.core.cache import cache
from django.core.management.base import BaseCommand

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None


class Command(BaseCommand):
    help = "Audita contadores de negações de módulos (module_deny_count:*) e exibe top N (cache ou Redis)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20, help="Limite de linhas exibidas")
        parser.add_argument("--redis-url", type=str, help="URL Redis direta (override)")
        parser.add_argument(
            "--reset", action="store_true", help="Zera todos os contadores module_deny_count:* encontrados"
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        redis_url = options.get("redis_url")
        items: list[tuple[str, int]] = []
        pattern = "module_deny_count:*"

        # 1. iter_keys direto
        if hasattr(cache, "iter_keys"):
            for k in cache.iter_keys(pattern):
                try:
                    val = cache.get(k)
                    items.append((k, int(val)))
                except Exception:
                    continue
        elif redis and (redis_url or cache.__class__.__name__.lower().startswith("rediscache")):
            # 2. Redis SCAN
            try:
                if redis_url:
                    r = redis.from_url(redis_url)
                else:
                    base_client = getattr(cache, "client", None)
                    if base_client and hasattr(base_client, "get_client"):
                        r = base_client.get_client(write=True)
                    else:
                        r = None
                if r:
                    cursor = 0
                    while True:
                        cursor, keys = r.scan(cursor=cursor, match=pattern, count=200)
                        for k in keys:
                            try:
                                raw = r.get(k)
                                if raw is None:
                                    continue
                                try:
                                    val = int(raw)
                                except Exception:
                                    continue
                                items.append((k.decode() if isinstance(k, bytes) else k, val))
                            except Exception:
                                continue
                        if cursor == 0:
                            break
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Falha Redis: {e}"))
        elif hasattr(cache, "_cache"):
            # 3. Heurística LocMem: inspeciona _cache
            internal = cache._cache
            try:
                import pickle

                seen = {}
                for k, raw in list(internal.items()):  # type: ignore
                    if not isinstance(k, str):
                        continue
                    pos = k.find("module_deny_count:")
                    if pos == -1:
                        continue
                    norm = k[pos:]
                    val = cache.get(norm)
                    if val is None:
                        cand = raw
                        if isinstance(cand, tuple) and len(cand) >= 2:
                            cand = cand[1]
                        if isinstance(cand, bytes):
                            with contextlib.suppress(Exception):
                                cand = pickle.loads(cand)
                        val = cand
                    try:
                        val = int(val)
                    except Exception:
                        continue
                    seen[norm] = val
                items.extend(seen.items())
            except Exception:
                pass
        else:
            # 4. última heurística (varrer dicts públicos)
            try:
                import pickle

                seen = {}
                for attr in dir(cache):
                    if attr.startswith("_"):
                        continue
                    try:
                        candidate = getattr(cache, attr)
                    except Exception:
                        continue
                    if not isinstance(candidate, dict):
                        continue
                    for k, raw in list(candidate.items()):
                        if not isinstance(k, str):
                            continue
                        pos = k.find("module_deny_count:")
                        if pos == -1:
                            continue
                        norm = k[pos:]
                        val = cache.get(norm)
                        if val is None:
                            cand = raw
                            if isinstance(cand, tuple) and len(cand) >= 2:
                                cand = cand[1]
                            if isinstance(cand, bytes):
                                with contextlib.suppress(Exception):
                                    cand = pickle.loads(cand)
                            val = cand
                        try:
                            val = int(val)
                        except Exception:
                            continue
                        seen[norm] = val
                if not seen:
                    self.stdout.write(self.style.WARNING("Backend sem suporte a listagem; use --redis-url."))
                items.extend(seen.items())
            except Exception:
                self.stdout.write(self.style.WARNING("Backend sem suporte a listagem; use --redis-url."))

        # Reset opcional
        if options.get("reset") and items:
            for k, _ in items:
                try:
                    cache.delete(k)
                except Exception:
                    continue
            self.stdout.write(self.style.SUCCESS(f"{len(items)} contadores resetados."))
            items = []

        items.sort(key=lambda x: x[1], reverse=True)
        if items:
            for k, v in items[:limit]:
                self.stdout.write(f"{k} => {v}")
        else:
            self.stdout.write("Nenhum contador encontrado.")
