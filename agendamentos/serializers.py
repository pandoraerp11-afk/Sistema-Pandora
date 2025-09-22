from rest_framework import serializers

from .models import Agendamento, AuditoriaAgendamento, Disponibilidade, Slot


class DisponibilidadeSerializer(serializers.ModelSerializer):
    profissional_nome = serializers.CharField(source="profissional.get_full_name", read_only=True)

    class Meta:
        model = Disponibilidade
        fields = "__all__"
        read_only_fields = ("tenant", "profissional")


class SlotSerializer(serializers.ModelSerializer):
    profissional_nome = serializers.CharField(source="profissional.get_full_name", read_only=True)
    disponivel = serializers.SerializerMethodField()

    class Meta:
        model = Slot
        fields = "__all__"
        read_only_fields = ("tenant", "profissional", "capacidade_utilizada")

    def get_disponivel(self, obj):
        return obj.disponivel


class AgendamentoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome_razao_social", read_only=True)
    profissional_nome = serializers.CharField(source="profissional.get_full_name", read_only=True)
    slot_info = serializers.SerializerMethodField(read_only=True)
    servico_nome = serializers.CharField(source="servico.nome_servico", read_only=True)
    servico_categoria = serializers.CharField(source="servico.categoria", read_only=True)

    class Meta:
        model = Agendamento
        fields = "__all__"
        read_only_fields = ("tenant", "status")

    def get_slot_info(self, obj):
        if obj.slot_id:
            return {
                "slot_id": obj.slot_id,
                "horario": obj.slot.horario,
                "profissional": obj.slot.profissional_id,
            }
        return None


class AuditoriaAgendamentoSerializer(serializers.ModelSerializer):
    user_nome = serializers.CharField(source="user.get_full_name", read_only=True)
    agendamento_servico = serializers.CharField(source="agendamento.servico.nome_servico", read_only=True, default=None)

    class Meta:
        model = AuditoriaAgendamento
        fields = "__all__"
        read_only_fields = ("agendamento", "user")


# --- V2 Serializers (scaffold) ---
class AgendamentoV2ListSerializer(serializers.ModelSerializer):
    cliente = serializers.SerializerMethodField()
    profissional = serializers.SerializerMethodField()
    servico = serializers.SerializerMethodField()
    slot = serializers.SerializerMethodField()

    class Meta:
        model = Agendamento
        fields = (
            "id",
            "status",
            "origem",
            "data_inicio",
            "data_fim",
            "cliente",
            "profissional",
            "servico",
            "slot",
            "metadata",
        )
        read_only_fields = fields

    def get_cliente(self, obj):
        if not obj.cliente_id:
            return None
        return {"id": obj.cliente_id, "nome": getattr(obj.cliente, "nome_razao_social", str(obj.cliente))}

    def get_profissional(self, obj):
        if not obj.profissional_id:
            return None
        return {"id": obj.profissional_id, "nome": obj.profissional.get_full_name()}

    def get_servico(self, obj):
        if not obj.servico_id:
            return None
        return {"id": obj.servico_id, "nome": getattr(obj.servico, "nome_servico", None)}

    def get_slot(self, obj):
        if not obj.slot_id:
            return None
        s = obj.slot
        return {"id": s.id, "horario": s.horario, "cap_total": s.capacidade_total, "cap_usada": s.capacidade_utilizada}


class AgendamentoV2DetailSerializer(AgendamentoV2ListSerializer):
    auditoria = serializers.SerializerMethodField()

    class Meta(AgendamentoV2ListSerializer.Meta):
        fields = AgendamentoV2ListSerializer.Meta.fields + ("auditoria",)

    def get_auditoria(self, obj):
        # Lazy import para evitar custo em listagem
        from .models import AuditoriaAgendamento

        eventos = AuditoriaAgendamento.objects.filter(agendamento=obj).order_by("-created_at")[:20]
        return [
            {
                "id": ev.id,
                "tipo": ev.tipo_evento,
                "de": ev.de_status,
                "para": ev.para_status,
                "ts": ev.created_at,
                "user": getattr(ev.user, "get_full_name", lambda: None)() if ev.user_id else None,
            }
            for ev in eventos
        ]


class AgendamentoV2CreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agendamento
        fields = ("cliente", "profissional", "slot", "data_inicio", "data_fim", "servico", "origem", "metadata")
        extra_kwargs = {
            "data_inicio": {"required": False, "allow_null": True},
            "data_fim": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        slot = attrs.get("slot")
        data_inicio = attrs.get("data_inicio")
        data_fim = attrs.get("data_fim")
        if not slot and (not data_inicio or not data_fim):
            raise serializers.ValidationError({"detail": "Informe slot ou data_inicio/data_fim"})
        # Autocompletar horários via slot quando fornecido e datas ausentes
        if slot and (not data_inicio or not data_fim):
            from datetime import timedelta

            attrs["data_inicio"] = slot.horario
            # Estimar data_fim: usar diferença padrão 30m ou derivar de disponibilidade
            dur_minutes = getattr(slot.disponibilidade, "duracao_slot_minutos", 30)
            attrs["data_fim"] = slot.horario + timedelta(minutes=dur_minutes)
            # Adicionar marcação no metadata (feito posteriormente no service)
        return attrs
