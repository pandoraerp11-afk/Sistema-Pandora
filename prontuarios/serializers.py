import logging

from rest_framework import serializers

from .models import Anamnese, Atendimento, FotoEvolucao, PerfilClinico

# Modelo Paciente removido – serializer correspondente excluído.

# ProcedimentoSerializer removido - agora use ServioSerializer do app servicos


class AtendimentoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome_razao_social", read_only=True)
    slot_info = serializers.SerializerMethodField(read_only=True)
    agendamento_id = serializers.IntegerField(source="agendamento.id", read_only=True)

    class Meta:
        model = Atendimento
        fields = "__all__"
        read_only_fields = ("origem_agendamento", "evento_agenda")

    def get_slot_info(self, obj):
        if obj.slot_id:
            # Log leve para monitorar usos legados de slot via Prontuários
            logging.getLogger(__name__).debug(
                "Atendimento %s com slot legado %s (agenda unificada centraliza capacidade no módulo Agendamentos).",
                obj.id,
                obj.slot_id,
            )
            return {
                "slot_id": obj.slot_id,
                "horario": obj.slot.horario,
                "profissional": obj.slot.profissional_id,
            }
        return None


class FotoEvolucaoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome_razao_social", read_only=True)

    class Meta:
        model = FotoEvolucao
        fields = "__all__"
        read_only_fields = (
            "tenant",
            "hash_arquivo",
            "tamanho_arquivo",
            "imagem_thumbnail",
            "imagem_webp",
            "video_poster",
            "resolucao",
            "video_meta",
        )


class AnamneseSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome_razao_social", read_only=True)

    class Meta:
        model = Anamnese
        fields = "__all__"


class PerfilClinicoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome_display", read_only=True)

    class Meta:
        model = PerfilClinico
        fields = "__all__"
        read_only_fields = ("tenant",)


"""Serializer de Disponibilidade removido: gestão centralizada na Agenda."""


"""Serializer de Slot removido: gestão centralizada na Agenda."""
