from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from servicos.models import Servico

# Regras de negócio IMUTÁVEIS: não mudar sem aprovação.
# Função pura de autorização para agendamento de serviço clínico.

CLINICAL_SCHEDULING_DENIED_MESSAGE = _("Sem permissão para agendar serviço clínico")


def can_schedule_clinical_service(user: User, servico: Servico) -> bool:
    """Retorna True se o usuário pode agendar o serviço clínico informado.

    Regras:
    1. Serviço deve estar ativo e marcado como clínico.
    2. Superuser sempre pode.
    3. Staff (profissional) pode se for is_staff.
    4. Grupo 'secretaria' (case insensitive em qualquer grupo) concede acesso.
    5. Cliente final: permitir se servico.disponivel_online estiver True e user
       tiver perfil cliente associado (heurística: grupo contendo 'cliente' ou não staff).
    6. Bloqueia se serviço não estiver disponível online para clientes não staff/secretaria.
    """
    if not servico.is_clinical or not servico.ativo:
        return False

    u = user
    if not u.is_authenticated:
        return False
    if u.is_superuser:
        return True
    if u.is_staff:
        return True

    # Secretaria
    if u.groups.filter(name__icontains="secretaria").exists():
        return True

    # Cliente portal: permitir apenas se disponível online
    if servico.disponivel_online:
        # Heurística simples: não staff, não secretaria e possui grupo com 'cliente' OU nenhum grupo especial
        if u.groups.filter(name__icontains="cliente").exists() or u.groups.count() == 0:
            return True

    # Métrica simples de negação (pode ser exportada futuramente)
    cache_key = "metric:clinical_schedule_denials"
    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, 3600)
    except Exception:
        pass
    return False


def get_clinical_denials_count():  # utilitário opcional para debug/monitor
    try:
        return cache.get("metric:clinical_schedule_denials", 0)
    except Exception:
        return 0
