"""Helpers de cálculo de risco para sessões de usuário."""

from django.utils import timezone


def build_context_maps(qs):
    """Gera mapas auxiliares para cálculo de riscos.

    Return:
        dicts: ips_por_usuario, paises_por_usuario
    """
    ips_por_usuario = {}
    paises_por_usuario = {}
    for s in qs:
        ips_por_usuario.setdefault(s.user_id, set()).add(s.ip_address)
        if s.pais:
            paises_por_usuario.setdefault(s.user_id, set()).add(s.pais)
    return ips_por_usuario, paises_por_usuario


def compute_risks(sessao, ips_por_usuario=None, paises_por_usuario=None):
    risks = []
    from .models import SessaoUsuario

    # Novo IP (primeira vez que aparece para o user em sessões anteriores ativas/inativas)
    if sessao.ip_address:
        # Se não estiver no mapa, construir fallback consulta
        if ips_por_usuario is not None:
            known_ips = ips_por_usuario.get(sessao.user_id, set()) - {sessao.ip_address}
            if sessao.ip_address not in known_ips and len(known_ips) == 0:
                risks.append("novo_ip")
        elif (
            not SessaoUsuario.objects.filter(user=sessao.user, ip_address=sessao.ip_address)
            .exclude(pk=sessao.pk)
            .exists()
        ):
            risks.append("novo_ip")
    # Inatividade longa
    if (timezone.now() - sessao.ultima_atividade).total_seconds() > 7200:  # >2h
        risks.append("inativo_longo")
    # Múltiplos IPs simultâneos
    if ips_por_usuario is not None and len(ips_por_usuario.get(sessao.user_id, [])) > 1:
        risks.append("multi_ip")
    # Variação geográfica simultânea
    if paises_por_usuario is not None and len(paises_por_usuario.get(sessao.user_id, [])) > 1:
        risks.append("geo_variacao")
    return risks


def session_to_dict(sessao, risks=None):
    return {
        "id": sessao.id,
        "user": sessao.user.get_full_name() or sessao.user.username,
        "username": sessao.user.username,
        "email": sessao.user.email,
        "ip_address": sessao.ip_address,
        "user_agent": (sessao.user_agent or "")[:160],
        "criada_em": sessao.criada_em.isoformat(),
        "ultima_atividade": sessao.ultima_atividade.isoformat(),
        "ativa": sessao.ativa,
        "risks": risks or [],
    }
