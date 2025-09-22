from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import AuditLog
from cotacoes.models import PropostaFornecedorItem

User = get_user_model()


class PropostaItemService:
    """Service para encapsular lógica de atualização inline de itens de proposta.

    Responsabilidades:
    - Validar campos recebidos.
    - Criar ou atualizar o item da proposta.
    - Recalcular total da proposta (delegado ao model save do item).
    - Registrar auditoria da alteração (antes/depois) com granularidade mínima.
    - Aplicar pequenas regras de negócio (ex: não permitir alteração se proposta bloqueada).
    """

    CAMPOS_NUMERICOS = {"preco_unitario"}
    CAMPOS_INT = {"prazo_entrega_dias"}
    CAMPOS_TEXT_LIMIT = {"observacao_item": 1000, "disponibilidade": 100}

    @classmethod
    def atualizar_inline(
        cls,
        proposta,
        item_cotacao,
        user,
        dados: dict[str, Any],
        tenant=None,
    ) -> tuple[PropostaFornecedorItem, bool, dict[str, Any]]:
        if not proposta.pode_editar():
            raise ValidationError("Proposta não editável")

        payload: dict[str, Any] = {}
        erros: dict[str, str] = {}

        # Normalização e validação
        for campo, valor in dados.items():
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                continue
            if campo in cls.CAMPOS_NUMERICOS:
                try:
                    v = Decimal(str(valor).replace(",", "."))
                    if v <= 0:
                        erros[campo] = "Deve ser maior que zero"
                    else:
                        payload[campo] = v
                except (InvalidOperation, ValueError):
                    erros[campo] = "Formato inválido"
            elif campo in cls.CAMPOS_INT:
                try:
                    iv = int(valor)
                    if iv < 0:
                        erros[campo] = "Não pode ser negativo"
                    else:
                        payload[campo] = iv
                except ValueError:
                    erros[campo] = "Inteiro inválido"
            elif campo in cls.CAMPOS_TEXT_LIMIT:
                limite = cls.CAMPOS_TEXT_LIMIT[campo]
                text = str(valor)[:limite]
                payload[campo] = text

        if erros:
            raise ValidationError(erros)

        # Defaults se item inexistente
        existente = PropostaFornecedorItem.objects.filter(proposta=proposta, item_cotacao=item_cotacao).first()
        created = False
        before_snapshot: dict[str, Any] = {}

        if not existente:
            # Requisitos mínimos
            if "preco_unitario" not in payload:
                payload["preco_unitario"] = Decimal("0.0001")
            if "prazo_entrega_dias" not in payload:
                payload["prazo_entrega_dias"] = 0
        else:
            before_snapshot = {
                "preco_unitario": str(existente.preco_unitario),
                "prazo_entrega_dias": existente.prazo_entrega_dias,
                "observacao_item": existente.observacao_item,
                "disponibilidade": existente.disponibilidade,
            }
            # Se não veio campo numérico manter existente
            if "preco_unitario" not in payload:
                payload["preco_unitario"] = existente.preco_unitario
            if "prazo_entrega_dias" not in payload:
                payload["prazo_entrega_dias"] = existente.prazo_entrega_dias

        with transaction.atomic():
            item, created = PropostaFornecedorItem.objects.update_or_create(
                proposta=proposta,
                item_cotacao=item_cotacao,
                defaults=payload,
            )

            after_snapshot = {
                "preco_unitario": str(item.preco_unitario),
                "prazo_entrega_dias": item.prazo_entrega_dias,
                "observacao_item": item.observacao_item,
                "disponibilidade": item.disponibilidade,
            }

            # Auditoria básica
            try:
                AuditLog.objects.create(
                    user=user,
                    tenant=tenant,
                    action_type="UPDATE" if not created else "CREATE",
                    change_message=f"Atualização inline item proposta {proposta.id}",
                    ip_address=None,
                    content_type=None,
                    object_id=item.id,
                )
            except Exception:  # pragma: no cover
                pass

        return item, created, {"before": before_snapshot, "after": after_snapshot}
