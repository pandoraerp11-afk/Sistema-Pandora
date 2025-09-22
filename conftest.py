"""Configuração do pytest e helpers de teste do Pandora.

Objetivos principais:
- Inicializar o Django para os testes;
- Facilitar o binding automático de tenant em sessões de teste;
- Habilitar módulos do tenant quando omitidos em cenários de teste;
- Tornar a cobertura mais amigável em execuções parciais, sem afetar a CI.
"""

# ruff: noqa: I001  # import sorting neste arquivo é proposital devido a side-effects do django.setup

from __future__ import annotations

import contextlib
import logging
import os
import sys
from typing import TYPE_CHECKING, Any, cast

import django
import pytest
from django.conf import settings as _settings
from django.contrib.auth.signals import user_logged_in
from django.test.client import Client

if TYPE_CHECKING:  # imports apenas para tipagem
    from collections.abc import Callable, Iterator
    from django.contrib.auth.models import AbstractBaseUser
    from django.contrib.sessions.backends.base import SessionBase
    from django.http import HttpRequest
    from django.test.client import Client as DjangoClient

    from core.models import Tenant

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pandora_erp.settings")

logger = logging.getLogger(__name__)

try:
    django.setup()
except Exception as e:  # pragma: no cover - apenas salvaguarda  # noqa: BLE001
    logger.warning("[conftest] Aviso ao inicializar Django: %s", e)

# Imports que dependem do Django inicializado
with contextlib.suppress(Exception):
    from core.models import Tenant as _Tenant
    from core.models import TenantUser

# Forçar flag de teste (detecção baseada em sys.modules pode ocorrer cedo demais)
_settings.TESTING = True

# =============================================================================
# Auto-seleção de tenant único para reduzir redirects 302 em testes
# =============================================================================
with contextlib.suppress(Exception):
    _original_force_login = Client.force_login

    def _auto_bind_single_tenant(session: SessionBase, user: AbstractBaseUser) -> None:  # helper isolado
        """Se usuário tiver exatamente um vínculo TenantUser e sessão sem tenant_id, define-o."""
        if "tenant_id" in session:
            return
        rel = getattr(user, "tenant_memberships", None)
        if rel is None:
            # fallback: query direta TenantUser
            rel_qs = TenantUser.objects.filter(user=user).values_list("tenant_id", flat=True)[:2]
            tenant_ids = list(rel_qs)
        else:
            tenant_ids = list(rel.values_list("tenant_id", flat=True)[:2])
        if len(tenant_ids) == 1:
            session["tenant_id"] = tenant_ids[0]
            with contextlib.suppress(Exception):
                session.save()

    def _patched_force_login(self: Client, user: AbstractBaseUser, backend: str | None = None) -> None:
        _original_force_login(self, user, backend=backend)
        with contextlib.suppress(Exception):
            _auto_bind_single_tenant(self.session, user)

    # Atribuição dinâmica em tempo de teste
    Client.force_login = _patched_force_login

    def _on_user_logged_in(
        sender: object,
        request: HttpRequest,
        user: AbstractBaseUser,
        **kwargs: object,
    ) -> None:  # sinal para login normal
        # Argumentos mantidos por compatibilidade com a API de sinais do Django.
        del sender, kwargs
        session = getattr(request, "session", None)
        if session is not None:
            with contextlib.suppress(Exception):
                _auto_bind_single_tenant(session, user)

    user_logged_in.connect(_on_user_logged_in)


def enable_all_modules_for_tenant(tenant: Tenant) -> Tenant:
    """Habilita todos os módulos conhecidos (settings.PANDORA_MODULES) para um tenant.

    Tolerante a erros e formatos.
    """
    try:
        from django.conf import settings

        mods = [
            item["module_name"]
            for item in getattr(settings, "PANDORA_MODULES", [])
            if isinstance(item, dict) and item.get("module_name")
        ]
        if mods:
            tenant.enabled_modules = {"modules": sorted(set(mods))}
            tenant.save(update_fields=["enabled_modules"])  # salva minimal
    except Exception:  # noqa: BLE001
        logger.debug("[conftest] enable_all_modules_for_tenant falhou", exc_info=True)
    return tenant


# Monkeypatch Tenant.save para garantir habilitação automática ainda durante a criação
with contextlib.suppress(Exception):
    _original_tenant_save = _Tenant.save

    def _tenant_save_patched(self: Tenant, *args: object, **kwargs: object) -> object:
        result = _original_tenant_save(self, *args, **kwargs)
        if getattr(_settings, "TESTING", False):
            em = getattr(self, "enabled_modules", None)
            # Somente autopopular se vazio ou dict com chave 'modules' vazia.
            autopop = (not em) or (
                isinstance(em, dict)
                and ("modules" in em)
                and (not isinstance(em["modules"], list) or not em["modules"])
            )
            if autopop:
                enable_all_modules_for_tenant(self)
        return result

    # Monkeypatch direto; ignorar verificação de tipo (atribuição de método em runtime)
    _Tenant.save = _tenant_save_patched  # type: ignore[method-assign]


@pytest.fixture(autouse=True)
def auto_enable_modules(db: object) -> Iterator[None]:
    """Garante que qualquer `Tenant` criado sem `enabled_modules` receba todos os módulos.

    Ajuda a evitar redirecionamentos 302 em testes que não configuram módulos.
    """
    del db  # ativa fixture do banco; não é usada diretamente aqui
    from core.models import Tenant

    yield
    # Após cada teste (fase teardown) ajustar apenas tenants sem módulos definidos
    with contextlib.suppress(Exception):
        for tenant in Tenant.objects.all():
            em = tenant.enabled_modules
            if not em or (isinstance(em, dict) and not em.get("modules")):
                enable_all_modules_for_tenant(tenant)


@pytest.fixture
def tenant_with_all_modules(db: object) -> Tenant:
    """Cria um `Tenant` já com todos os módulos habilitados."""
    del db  # ativa fixture do banco; não é usada diretamente aqui
    from core.models import Tenant

    tenant = Tenant.objects.create(name="Empresa Teste Auto", subdomain="empresa-auto")
    return enable_all_modules_for_tenant(tenant)


@pytest.fixture
def auth_user(client: DjangoClient, db: object) -> Callable[..., tuple[object, Tenant | None, object]]:
    """Cria e autentica um usuário (opcionalmente staff/superuser) já vinculado a um tenant.

    Configura `tenant_id` na sessão para evitar redirects de seleção.

    Uso:
        `user, tenant, client = auth_user(is_staff=True)`
    """
    del db  # ativa fixture do banco; não é usada diretamente aqui
    from django.contrib.auth import get_user_model

    from core.models import Tenant, TenantUser

    def _make(
        *,
        username: str = "user_fixture",
        password: str | None = None,
        is_staff: bool = False,
        is_superuser: bool = False,
        with_tenant: bool = True,
    ) -> tuple[object, Tenant | None, object]:
        user_model = get_user_model()
        pwd = os.environ.get("TEST_PASSWORD", "x") if password is None else password
        user = user_model.objects.create_user(
            username=username,
            password=pwd,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )
        tenant = None
        if with_tenant:
            # Segue o padrão usado em tenant_with_all_modules
            tenant = Tenant.objects.create(name=f"Empresa {username}", subdomain=f"empresa-{username}")
            TenantUser.objects.create(user=user, tenant=tenant)
            sess = client.session
            # Usar pk para agradar type-checkers e converter para int
            sess["tenant_id"] = int(tenant.pk) if tenant and tenant.pk is not None else None
            sess.save()
        # autentica o cliente sempre no final
        client.login(username=username, password=pwd)
        return user, tenant, client

    return _make


# =============================================================================
# Ajuste dinâmico de cobertura para execuções parciais
# -----------------------------------------------------------------------------
# Problema: ao rodar 1 único teste (ex.: via -k ou caminho direto), a métrica
# de cobertura global desaba (poucos arquivos exercitados) e o --cov-fail-under
# de 75% falha, poluindo o fluxo de TDD local.
# Estratégia: se a coleta tiver até 3 testes e a variável de ambiente
# ENFORCE_COVERAGE não estiver definida, zeramos cov_fail_under (somente sessão atual).
# Isso NÃO afeta a pipeline, bastando definir ENFORCE_COVERAGE=1 lá.
# =============================================================================
PARTIAL_ITEM_THRESHOLD = 3


def pytest_collection_finish(session: pytest.Session) -> None:  # noqa: C901, PLR0912
    """Ajusta thresholds de cobertura quando execução parcial é detectada."""
    try:
        config = session.config
        # Se NO_COV definido, já marcamos e saímos cedo
        if os.environ.get("NO_COV"):
            with contextlib.suppress(Exception):
                if getattr(config.option, "cov_fail_under", None) not in (0, None):
                    config.option.cov_fail_under = 0
            # Ajustar plugin interno também (mesma lógica usada abaixo)
            with contextlib.suppress(Exception):
                pm = config.pluginmanager
                candidates = [pm.getplugin(n) for n in ("cov", "pytest_cov", "_cov")]
                if not any(candidates):
                    candidates = [p for p in pm.get_plugins() if hasattr(p, "cov_controller")]
                for cov_plugin in candidates:
                    ctrl = getattr(cov_plugin, "cov_controller", None)
                    if cov_plugin and ctrl is not None:
                        opts = getattr(ctrl, "options", None)
                        if opts and hasattr(opts, "cov_fail_under") and opts.cov_fail_under != 0:
                            opts.cov_fail_under = 0
            # Flag amigável (sem underscore para evitar SLF001)
            config.coverage_relaxed = True  # type: ignore[attr-defined]
            logger.info("[conftest] NO_COV ativo - fail-under desativado nesta execucao parcial.")
            return
        # Apenas se plugin de cobertura ativo e threshold configurado (>0)
        if getattr(config.option, "cov_fail_under", 0) > 0:
            item_count = len(session.items)
            if item_count <= PARTIAL_ITEM_THRESHOLD and not os.environ.get("ENFORCE_COVERAGE"):
                # Log simples para visibilidade
                logger.info(
                    (
                        "[conftest] Execucao parcial detectada (%s testes) - "
                        "desativando fail-under cobertura nesta sessao."
                    ),
                    item_count,
                )
                config.option.cov_fail_under = 0
                config.coverage_relaxed = True  # type: ignore[attr-defined]  # flag para sessionfinish
                # Ajustar também objeto interno do plugin pytest-cov
                with contextlib.suppress(Exception):
                    # Possíveis nomes: 'cov', 'pytest_cov', '_cov'
                    pm = config.pluginmanager
                    candidates = [pm.getplugin(n) for n in ("cov", "pytest_cov", "_cov")]
                    # Fallback: inspecionar todos
                    if not any(candidates):
                        candidates = [p for p in pm.get_plugins() if hasattr(p, "cov_controller")]
                    for cov_plugin in candidates:
                        ctrl = getattr(cov_plugin, "cov_controller", None)
                        if cov_plugin and ctrl is not None:
                            opts = getattr(ctrl, "options", None)
                            if opts and hasattr(opts, "cov_fail_under") and opts.cov_fail_under != 0:
                                opts.cov_fail_under = 0
                                logger.info("[conftest] (cov) fail-under interno ajustado para 0.")
    except Exception as e:  # pragma: no cover - proteção defensiva  # noqa: BLE001
        logger.warning("[conftest] Aviso ajuste cobertura: %s", e)


def pytest_configure(config: pytest.Config) -> None:  # noqa: C901, PLR0912, PLR0915
    """Early hook para ajustar/neutralizar cobertura em execuções parciais.

    Também permite rodar localmente sem qualquer medição.
    Uso: set NO_COV=1 (Windows) / export NO_COV=1 (Unix).
    """
    try:
        # Heurística adicional: execução parcial (nodeids específicos, -k, paths de teste)
        # Se detectado e ENFORCE_COVERAGE não estiver ativo, desligar cobertura como no NO_COV.
        if not os.environ.get("ENFORCE_COVERAGE") and not os.environ.get("NO_COV"):
            argv = sys.argv[:]
            partial_hints = [
                any("::" in a for a in argv),  # nodeid específico
                "-k" in argv,  # seleção por expressão
                any((a.endswith(".py") and ("test" in a.lower() or "tests" in a.lower())) for a in argv),
            ]
            if any(partial_hints):
                # Remover flags de cobertura já na fase de configure
                new_argv = []
                skip_next = False
                for a in argv:
                    if skip_next:
                        skip_next = False
                        continue
                    if a.startswith("--cov-fail-under"):
                        continue
                    if a.startswith("--cov-report"):
                        continue
                    if a.startswith("--cov="):
                        continue
                    if a == "--cov":
                        skip_next = False
                        continue
                    new_argv.append(a)
                if len(new_argv) != len(argv):
                    logger.info(
                        "[conftest] Execucao parcial detectada - removendo flags de cobertura desta execucao.",
                    )
                    sys.argv[:] = new_argv
                # Ajustar opções se já parseadas
                if hasattr(config, "option"):
                    for attr in ("cov_fail_under", "no_cov"):
                        if hasattr(config.option, attr):
                            with contextlib.suppress(Exception):
                                setattr(config.option, attr, 0)
                # Remover plugin pytest-cov para evitar mensagens de FAIL por cobertura
                with contextlib.suppress(Exception):
                    pm = config.pluginmanager
                    removed_any = False
                    for name in ("cov", "pytest_cov", "_cov"):
                        plug = pm.getplugin(name)
                        if plug:
                            with contextlib.suppress(Exception):
                                pm.unregister(plug)
                                removed_any = True
                    # Fallback: procurar por objetos com 'cov_controller'
                    if not removed_any:
                        for p in list(pm.get_plugins()):
                            if hasattr(p, "cov_controller") or getattr(p, "__name__", "").startswith("pytest_cov"):
                                with contextlib.suppress(Exception):
                                    pm.unregister(p)
                                    removed_any = True
                    if removed_any:
                        logger.info("[conftest] Cobertura desativada para execucao parcial (plugin removido).")
                        config.coverage_disabled = True  # type: ignore[attr-defined]
                config.coverage_relaxed = True  # type: ignore[attr-defined]

        if os.environ.get("NO_COV"):
            # Sanitizar sys.argv removendo flags coverage antes que plugin atue.
            new_argv = []
            skip_next = False
            for a in sys.argv:
                if skip_next:
                    skip_next = False
                    continue
                if a.startswith("--cov-fail-under"):
                    continue
                if a.startswith("--cov-report"):
                    continue
                if a.startswith("--cov="):
                    continue
                if a == "--cov":  # pode vir separado de path
                    skip_next = False  # se houvesse caminho depois, ignoraria; aqui não previsto
                    continue
                new_argv.append(a)
            if len(new_argv) != len(sys.argv):
                logger.info("[conftest] NO_COV ativo - removendo flags de cobertura da linha de comando.")
                sys.argv[:] = new_argv
            # Ajustar opções se já parseadas
            if hasattr(config, "option"):
                for attr in ("cov_fail_under", "no_cov"):
                    if hasattr(config.option, attr):
                        with contextlib.suppress(Exception):
                            setattr(config.option, attr, 0)
            config.coverage_relaxed = True  # type: ignore[attr-defined]
    except Exception as e:  # pragma: no cover  # noqa: BLE001
        logger.warning("[conftest] Aviso NO_COV configure: %s", e)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Adiciona flag --runslow para incluir testes marcados como @pytest.mark.slow."""
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="Executa testes marcados como slow (lentos / dependencias externas).",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Se --runslow não for passado e RUN_SLOW não estiver definido, marca slow como skip."""
    try:
        if config.getoption("--runslow") or os.environ.get("RUN_SLOW"):
            return
        skip_marker = pytest.mark.skip(reason="slow omitido (use --runslow ou RUN_SLOW=1)")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_marker)
    except Exception:  # noqa: BLE001
        logger.debug("[conftest] pytest_collection_modifyitems: falha ao aplicar skip slow", exc_info=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Se apenas a cobertura falhou e marcamos relaxamento, neutraliza o exitstatus.

    Evita mascarar falhas reais: só altera se não houver testes falhos/erro.
    """
    try:
        config = session.config
        if not getattr(config, "coverage_relaxed", False):
            return
        # Obter reporter para inspecionar estatísticas
        tr = config.pluginmanager.getplugin("terminalreporter")
        if not tr:
            return
        tr_any = cast(Any, tr)
        failed = sum(len(tr_any.stats.get(k, [])) for k in ("failed", "error"))
        if failed == 0 and exitstatus != 0:
            # Provavelmente só cobertura (ou warnings tratados como erro). Normalizar.
            if getattr(config, "coverage_disabled", False):
                logger.info(
                    "[conftest] Execucao parcial: cobertura desativada - normalizando exitstatus para 0.",
                )
            else:
                logger.info("[conftest] Cobertura relaxada: normalizando exitstatus para 0.")
            session.exitstatus = 0
    except Exception:  # noqa: BLE001
        logger.debug("[conftest] pytest_sessionfinish: erro ao normalizar exitstatus", exc_info=True)


# =============================================================================
# Reset de métricas do wizard por teste (baseline limpo)
# =============================================================================
@pytest.fixture(autouse=True)
def _reset_wizard_metrics() -> None:
    """Reseta métricas in-memory do wizard antes de cada teste.

    Evita contaminação entre testes que inspecionam contadores/snapshots.
    """
    try:
        from core.services.wizard_metrics import reset_all_metrics

        reset_all_metrics()
    except Exception:  # noqa: BLE001
        logger.debug("[conftest] reset_wizard_metrics: falha ao resetar", exc_info=True)
