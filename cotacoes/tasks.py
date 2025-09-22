"""
Tasks Celery para cotações e portal fornecedor.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .metrics import health_check_component, update_state_metrics

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def notificar_nova_cotacao(self, cotacao_id, fornecedor_ids=None):
    """
    Notifica fornecedores sobre nova cotação disponível.

    Args:
        cotacao_id: ID da cotação
        fornecedor_ids: Lista de IDs de fornecedores (opcional, notifica todos se None)
    """
    try:
        from fornecedores.models import Fornecedor
        from portal_fornecedor.models import AcessoFornecedor

        from .models import Cotacao

        cotacao = Cotacao.objects.get(id=cotacao_id)

        # Definir fornecedores a notificar
        if fornecedor_ids:
            fornecedores = Fornecedor.objects.filter(
                id__in=fornecedor_ids,
                tenant=cotacao.tenant,
                portal_ativo=True,
                status="active",
                status_homologacao="aprovado",
            )
        else:
            fornecedores = Fornecedor.objects.filter(
                tenant=cotacao.tenant, portal_ativo=True, status="active", status_homologacao="aprovado"
            )

        emails_enviados = 0
        for fornecedor in fornecedores:
            # Verificar se pode participar
            pode, _ = cotacao.pode_receber_proposta(fornecedor)
            if not pode:
                continue

            # Buscar usuários com acesso ao portal
            acessos = AcessoFornecedor.objects.filter(fornecedor=fornecedor, ativo=True, usuario__is_active=True)

            for acesso in acessos:
                try:
                    # Preparar contexto do email
                    contexto = {
                        "cotacao": cotacao,
                        "fornecedor": fornecedor,
                        "usuario": acesso.usuario,
                        "prazo_proposta": cotacao.prazo_proposta,
                        "total_itens": cotacao.itens.count(),
                        "link_portal": f"{settings.FRONTEND_URL}/portal/fornecedor/cotacoes/{cotacao.id}/",
                    }

                    # Renderizar email
                    assunto = f"Nova Cotação Disponível: {cotacao.codigo}"
                    corpo_html = render_to_string("emails/nova_cotacao_fornecedor.html", contexto)
                    corpo_texto = render_to_string("emails/nova_cotacao_fornecedor.txt", contexto)

                    # Enviar email
                    send_mail(
                        subject=assunto,
                        message=corpo_texto,
                        html_message=corpo_html,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[acesso.usuario.email],
                        fail_silently=False,
                    )

                    emails_enviados += 1

                except Exception as e:
                    logger.error(f"Erro ao enviar email para {acesso.usuario.email}: {e}")

        logger.info(f"Notificação cotação {cotacao.codigo}: {emails_enviados} emails enviados")
        return emails_enviados

    except Exception as e:
        logger.error(f"Erro na notificação de cotação {cotacao_id}: {e}")
        raise


@shared_task(bind=True)
def verificar_cotacoes_vencidas(self):
    """
    Verifica cotações com prazo vencido e atualiza status.
    """
    try:
        from .models import Cotacao

        cotacoes_vencidas = Cotacao.objects.filter(status="aberta", prazo_proposta__lt=timezone.now())

        total_encerradas = 0
        for cotacao in cotacoes_vencidas:
            # Verificar se tem propostas
            if cotacao.propostas.filter(status="enviada").exists():
                cotacao.status = "aguardando_decisao"
            else:
                cotacao.status = "encerrada"
                cotacao.data_encerramento = timezone.now()

            cotacao.observacoes_internas += f"\n\nEncerrrada automaticamente em {timezone.now()} - prazo vencido"
            cotacao.save(update_fields=["status", "data_encerramento", "observacoes_internas", "updated_at"])
            total_encerradas += 1

        if total_encerradas > 0:
            logger.info(f"Encerrradas automaticamente {total_encerradas} cotações vencidas")

        return total_encerradas

    except Exception as e:
        logger.error(f"Erro ao verificar cotações vencidas: {e}")
        raise


@shared_task(bind=True)
def lembrete_prazo_cotacao(self, dias_antecedencia=2):
    """
    Envia lembrete sobre cotações próximas do prazo.

    Args:
        dias_antecedencia: Quantos dias antes do prazo enviar lembrete
    """
    try:
        from portal_fornecedor.models import AcessoFornecedor

        from .models import Cotacao

        data_limite = timezone.now() + timedelta(days=dias_antecedencia)

        cotacoes_proximas = Cotacao.objects.filter(
            status="aberta", prazo_proposta__lte=data_limite, prazo_proposta__gt=timezone.now()
        )

        emails_enviados = 0
        for cotacao in cotacoes_proximas:
            # Buscar fornecedores que ainda não enviaram proposta
            fornecedores_sem_proposta = cotacao.tenant.fornecedores.filter(
                portal_ativo=True, status="active", status_homologacao="aprovado"
            ).exclude(propostas__cotacao=cotacao, propostas__status__in=["enviada", "selecionada"])

            for fornecedor in fornecedores_sem_proposta:
                acessos = AcessoFornecedor.objects.filter(fornecedor=fornecedor, ativo=True, usuario__is_active=True)

                for acesso in acessos:
                    try:
                        contexto = {
                            "cotacao": cotacao,
                            "fornecedor": fornecedor,
                            "usuario": acesso.usuario,
                            "horas_restantes": (cotacao.prazo_proposta - timezone.now()).total_seconds() / 3600,
                            "link_portal": f"{settings.FRONTEND_URL}/portal/fornecedor/cotacoes/{cotacao.id}/",
                        }

                        assunto = f"⏰ Lembrete: Cotação {cotacao.codigo} - Prazo expira em breve"
                        corpo_html = render_to_string("emails/lembrete_cotacao.html", contexto)

                        send_mail(
                            subject=assunto,
                            message=f"A cotação {cotacao.codigo} expira em breve. Acesse o portal para enviar sua proposta.",
                            html_message=corpo_html,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[acesso.usuario.email],
                            fail_silently=False,
                        )

                        emails_enviados += 1

                    except Exception as e:
                        logger.error(f"Erro ao enviar lembrete para {acesso.usuario.email}: {e}")

        logger.info(f"Lembretes enviados: {emails_enviados}")
        return emails_enviados

    except Exception as e:
        logger.error(f"Erro ao enviar lembretes: {e}")
        raise


@shared_task(bind=True)
def atualizar_metricas_portal(self):
    """
    Atualiza métricas de estado do portal (Gauges).
    """
    try:
        update_state_metrics()
        logger.info("Métricas de estado atualizadas")
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar métricas: {e}")
        raise


@shared_task(bind=True)
def gerar_relatorio_cotacoes(self, tenant_id, periodo_dias=30):
    """
    Gera relatório de cotações para um tenant.

    Args:
        tenant_id: ID do tenant
        periodo_dias: Período do relatório em dias
    """
    try:
        from decimal import Decimal

        from django.db import models

        from core.models import Tenant

        from .models import Cotacao, PropostaFornecedor

        tenant = Tenant.objects.get(id=tenant_id)
        data_inicio = timezone.now() - timedelta(days=periodo_dias)

        # Estatísticas do período
        cotacoes = Cotacao.objects.filter(tenant=tenant, created_at__gte=data_inicio)

        propostas = PropostaFornecedor.objects.filter(cotacao__tenant=tenant, created_at__gte=data_inicio)

        stats = {
            "total_cotacoes": cotacoes.count(),
            "cotacoes_abertas": cotacoes.filter(status="aberta").count(),
            "cotacoes_encerradas": cotacoes.filter(status="encerrada").count(),
            "total_propostas": propostas.count(),
            "propostas_enviadas": propostas.filter(status="enviada").count(),
            "propostas_selecionadas": propostas.filter(status="selecionada").count(),
            "valor_total_cotacoes": cotacoes.aggregate(total=models.Sum("valor_estimado"))["total"] or Decimal("0"),
            "valor_total_propostas": propostas.filter(status="enviada").aggregate(total=models.Sum("total_estimado"))[
                "total"
            ]
            or Decimal("0"),
        }

        # Calcular economia estimada
        if stats["valor_total_cotacoes"] > 0 and stats["valor_total_propostas"] > 0:
            stats["economia_estimada"] = stats["valor_total_cotacoes"] - stats["valor_total_propostas"]
            stats["percentual_economia"] = (stats["economia_estimada"] / stats["valor_total_cotacoes"]) * 100

        # TODO: Salvar relatório ou enviar por email
        logger.info(f"Relatório gerado para tenant {tenant.nome}: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Erro ao gerar relatório: {e}")
        raise


@shared_task(bind=True)
def health_check_portal(self):
    """
    Executa health check do sistema de cotações e portal.
    """
    try:
        results = {}

        # Verificar banco de dados
        @health_check_component("database")
        def check_database():
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True, "Database OK"

        # Verificar Redis (se configurado)
        @health_check_component("redis")
        def check_redis():
            try:
                from django.core.cache import cache

                cache.set("health_check", "ok", 30)
                return cache.get("health_check") == "ok", "Redis OK"
            except Exception as e:
                return False, f"Redis Error: {e}"

        # Verificar Email
        @health_check_component("email")
        def check_email():
            try:
                from django.core.mail import get_connection

                connection = get_connection()
                return connection.open(), "Email OK"
            except Exception as e:
                return False, f"Email Error: {e}"

        # Executar checks
        results["database"] = check_database()
        results["redis"] = check_redis()
        results["email"] = check_email()

        # Status geral
        all_ok = all(result[0] for result in results.values())
        results["status"] = "healthy" if all_ok else "unhealthy"

        logger.info(f"Health check completed: {results}")
        return results

    except Exception as e:
        logger.error(f"Erro no health check: {e}")
        return {"status": "error", "error": str(e)}
