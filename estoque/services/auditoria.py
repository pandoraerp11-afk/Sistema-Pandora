"""
Serviço de Auditoria Avançada para Estoque
Implementa hash chain para integridade imutável dos logs
"""

import hashlib
import json
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import transaction

from estoque.models import LogAuditoriaEstoque, MovimentoEstoque

User = get_user_model()


class AuditoriaService:
    """Serviço para auditoria com hash chain"""

    @staticmethod
    def gerar_hash(payload, hash_previo=None):
        """
        Gera hash SHA-256 do payload + hash anterior para criar cadeia
        """
        # Serializar payload de forma determinística
        payload_str = json.dumps(payload, sort_keys=True, default=str)

        # Combinar com hash anterior
        conteudo = f"{hash_previo or ''}{payload_str}"

        return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()

    @staticmethod
    def obter_ultimo_hash():
        """Obtém o último hash da cadeia"""
        ultimo_log = LogAuditoriaEstoque.objects.order_by("-criado_em").first()
        return ultimo_log.hash_atual if ultimo_log else None

    @classmethod
    def criar_log_auditoria(cls, movimento, usuario, snapshot_antes=None, snapshot_depois=None, evidencias_ids=None):
        """
        Cria log de auditoria com hash chain
        """
        with transaction.atomic():
            # Obter hash anterior
            hash_previo = cls.obter_ultimo_hash()

            # Preparar payload para hash
            payload = {
                "movimento_id": movimento.id,
                "tipo": movimento.tipo,
                "produto_id": movimento.produto_id,
                "quantidade": str(movimento.quantidade),
                "custo_unitario": str(movimento.custo_unitario_snapshot),
                "usuario_id": usuario.id if usuario else None,
                "timestamp": movimento.criado_em.isoformat(),
                "solicitante_tipo": movimento.solicitante_tipo,
                "solicitante_id": movimento.solicitante_id,
                "solicitante_nome": movimento.solicitante_nome_cache,
                "aprovacao_status": movimento.aprovacao_status,
                "evidencias_ids": evidencias_ids or [],
                "snapshot_antes": snapshot_antes,
                "snapshot_depois": snapshot_depois,
            }

            # Gerar hash atual
            hash_atual = cls.gerar_hash(payload, hash_previo)

            # Determinar tipo especial
            tipo_especial = None
            if movimento.tipo in ["DESCARTE", "PERDA", "VENCIMENTO"]:
                tipo_especial = movimento.tipo

            # Criar log
            log = LogAuditoriaEstoque.objects.create(
                movimento=movimento,
                tenant=movimento.tenant,
                snapshot_antes=snapshot_antes,
                snapshot_depois=snapshot_depois,
                hash_previo=hash_previo,
                hash_atual=hash_atual,
                evidencias_ids=evidencias_ids,
                solicitante_nome_cache=movimento.solicitante_nome_cache,
                tipo_especial=tipo_especial,
                usuario=usuario,
            )

            return log

    @classmethod
    def validar_integridade_chain(cls, desde_id=None):
        """
        Valida integridade da cadeia de hash
        """
        query = LogAuditoriaEstoque.objects.order_by("criado_em")
        if desde_id:
            query = query.filter(id__gte=desde_id)

        logs = list(query)

        resultado = {"valido": True, "total_verificados": len(logs), "erros": []}

        hash_anterior = None
        for i, log in enumerate(logs):
            # Reconstruir payload
            movimento = log.movimento
            payload = {
                "movimento_id": movimento.id,
                "tipo": movimento.tipo,
                "produto_id": movimento.produto_id,
                "quantidade": str(movimento.quantidade),
                "custo_unitario": str(movimento.custo_unitario_snapshot),
                "usuario_id": log.usuario_id,
                "timestamp": movimento.criado_em.isoformat(),
                "solicitante_tipo": movimento.solicitante_tipo,
                "solicitante_id": movimento.solicitante_id,
                "solicitante_nome": movimento.solicitante_nome_cache,
                "aprovacao_status": movimento.aprovacao_status,
                "evidencias_ids": log.evidencias_ids or [],
                "snapshot_antes": log.snapshot_antes,
                "snapshot_depois": log.snapshot_depois,
            }

            # Verificar hash
            hash_esperado = cls.gerar_hash(payload, hash_anterior)

            if hash_esperado != log.hash_atual:
                resultado["valido"] = False
                resultado["erros"].append(
                    {
                        "log_id": log.id,
                        "posicao": i,
                        "hash_esperado": hash_esperado,
                        "hash_encontrado": log.hash_atual,
                        "erro": "Hash não confere - possível adulteração",
                    }
                )

            # Verificar se hash_previo bate com anterior
            if log.hash_previo != hash_anterior:
                resultado["valido"] = False
                resultado["erros"].append(
                    {
                        "log_id": log.id,
                        "posicao": i,
                        "hash_previo_esperado": hash_anterior,
                        "hash_previo_encontrado": log.hash_previo,
                        "erro": "Cadeia quebrada - hash anterior não confere",
                    }
                )

            hash_anterior = log.hash_atual

        return resultado

    @staticmethod
    def exportar_auditoria_json(movimento_ids=None, data_inicio=None, data_fim=None):
        """
        Exporta dados de auditoria em formato JSON para análise forense
        """
        query = LogAuditoriaEstoque.objects.select_related("movimento", "usuario").order_by("criado_em")

        if movimento_ids:
            query = query.filter(movimento_id__in=movimento_ids)
        if data_inicio:
            query = query.filter(criado_em__gte=data_inicio)
        if data_fim:
            query = query.filter(criado_em__lte=data_fim)

        logs = []
        for log in query:
            mov = log.movimento
            logs.append(
                {
                    "log_id": log.id,
                    "movimento_id": mov.id,
                    "tipo_movimento": mov.tipo,
                    "produto_id": mov.produto_id,
                    "deposito_origem_id": mov.deposito_origem_id,
                    "deposito_destino_id": mov.deposito_destino_id,
                    "quantidade": str(mov.quantidade),
                    "custo_unitario": str(mov.custo_unitario_snapshot),
                    "valor_estimado": str(mov.valor_estimado),
                    "usuario_executante": mov.usuario_executante.username if mov.usuario_executante else None,
                    "solicitante": {
                        "tipo": mov.solicitante_tipo,
                        "id": mov.solicitante_id,
                        "nome_cache": mov.solicitante_nome_cache,
                    },
                    "aprovacao_status": mov.aprovacao_status,
                    "ref_externa": mov.ref_externa,
                    "motivo": mov.motivo,
                    "metadata": mov.metadata,
                    "evidencias_ids": log.evidencias_ids,
                    "tipo_especial": log.tipo_especial,
                    "hash_previo": log.hash_previo,
                    "hash_atual": log.hash_atual,
                    "snapshot_antes": log.snapshot_antes,
                    "snapshot_depois": log.snapshot_depois,
                    "timestamp": log.criado_em.isoformat(),
                }
            )

        return {"export_timestamp": datetime.now().isoformat(), "total_logs": len(logs), "logs": logs}


class AuditoriaForenseService:
    """Serviços de análise forense para auditoria"""

    @staticmethod
    def detectar_padroes_suspeitos(data_inicio=None, data_fim=None):
        """
        Detecta padrões suspeitos nos movimentos
        """

        from django.db.models import Count, Q, Sum

        # Consultar movimentos no período
        query = MovimentoEstoque.objects.all()
        if data_inicio:
            query = query.filter(criado_em__gte=data_inicio)
        if data_fim:
            query = query.filter(criado_em__lte=data_fim)

        alertas = []

        # 1. Muitas perdas/descartes do mesmo usuário
        perdas_por_usuario = (
            query.filter(tipo__in=["PERDA", "DESCARTE", "VENCIMENTO"])
            .values("usuario_executante__username")
            .annotate(total=Count("id"), valor_total=Sum("valor_estimado"))
            .filter(total__gt=5)
            .order_by("-total")
        )

        for item in perdas_por_usuario:
            alertas.append(
                {
                    "tipo": "PERDAS_EXCESSIVAS_USUARIO",
                    "usuario": item["usuario_executante__username"],
                    "total_movimentos": item["total"],
                    "valor_total": float(item["valor_total"] or 0),
                    "criticidade": "ALTA" if item["total"] > 10 else "MEDIA",
                }
            )

        # 2. Movimentos fora do horário comercial
        if data_inicio and data_fim:
            movimentos_noturnos = query.filter(Q(criado_em__time__lt="06:00") | Q(criado_em__time__gt="22:00")).count()

            if movimentos_noturnos > 0:
                alertas.append(
                    {"tipo": "MOVIMENTOS_FORA_HORARIO", "total": movimentos_noturnos, "criticidade": "MEDIA"}
                )

        # 3. Concentração de ajustes negativos
        ajustes_negativos = (
            query.filter(tipo="AJUSTE_NEG")
            .values("produto_id")
            .annotate(total=Count("id"), quantidade_total=Sum("quantidade"))
            .filter(total__gt=3)
            .order_by("-total")
        )

        for item in ajustes_negativos:
            alertas.append(
                {
                    "tipo": "AJUSTES_NEGATIVOS_CONCENTRADOS",
                    "produto_id": item["produto_id"],
                    "total_ajustes": item["total"],
                    "quantidade_total": float(item["quantidade_total"]),
                    "criticidade": "MEDIA",
                }
            )

        return {
            "periodo": {
                "inicio": data_inicio.isoformat() if data_inicio else None,
                "fim": data_fim.isoformat() if data_fim else None,
            },
            "total_alertas": len(alertas),
            "alertas": alertas,
        }

    @staticmethod
    def rastrear_produto(produto_id, dias=30):
        """
        Rastreia histórico completo de um produto
        """
        from datetime import timedelta

        data_limite = datetime.now() - timedelta(days=dias)

        movimentos = (
            MovimentoEstoque.objects.filter(produto_id=produto_id, criado_em__gte=data_limite)
            .select_related("usuario_executante", "deposito_origem", "deposito_destino")
            .order_by("criado_em")
        )

        historico = []
        for mov in movimentos:
            historico.append(
                {
                    "id": mov.id,
                    "timestamp": mov.criado_em.isoformat(),
                    "tipo": mov.tipo,
                    "quantidade": float(mov.quantidade),
                    "custo_unitario": float(mov.custo_unitario_snapshot),
                    "valor_total": float(mov.valor_estimado),
                    "deposito_origem": mov.deposito_origem.codigo if mov.deposito_origem else None,
                    "deposito_destino": mov.deposito_destino.codigo if mov.deposito_destino else None,
                    "usuario": mov.usuario_executante.username if mov.usuario_executante else None,
                    "solicitante": {
                        "tipo": mov.solicitante_tipo,
                        "nome": mov.solicitante_nome_cache,
                    },
                    "aprovacao_status": mov.aprovacao_status,
                    "ref_externa": mov.ref_externa,
                    "motivo": mov.motivo,
                }
            )

        return {
            "produto_id": produto_id,
            "periodo_dias": dias,
            "total_movimentos": len(historico),
            "historico": historico,
        }
