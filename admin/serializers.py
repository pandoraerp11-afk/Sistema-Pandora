# admin/serializers.py (VERSÃO ATUALIZADA E CORRIGIDA)

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import AdminActivity, SystemAlert, TenantBackup, TenantConfiguration, TenantUsageReport
from .models import SystemConfiguration as SystemConfigModel

User = get_user_model()

# --- Serializers para os modelos do Admin Dashboard ---


class SystemAlertSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True, allow_null=True)
    assigned_to_name = serializers.CharField(source="assigned_to.get_full_name", read_only=True, allow_null=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = SystemAlert
        fields = "__all__"


class TenantConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantConfiguration
        fields = "__all__"


class AdminActivitySerializer(serializers.ModelSerializer):
    # CORREÇÃO: Ajustado para fornecer os dados que o template espera
    user_email = serializers.EmailField(source="admin_user.email", read_only=True)
    action = serializers.CharField(source="get_action_display", read_only=True)  # Usando o display da ação
    content_type = serializers.CharField(source="resource_type", read_only=True)
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = AdminActivity
        # CORREÇÃO: Campos ajustados para o que o template precisa
        fields = ("timestamp", "user_email", "action", "content_type", "description")


class TenantBackupSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    duration = serializers.ReadOnlyField()
    file_size_mb = serializers.SerializerMethodField()

    class Meta:
        model = TenantBackup
        fields = "__all__"

    def get_file_size_mb(self, obj):
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return 0


class SystemConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfigModel
        fields = "__all__"


class TenantUsageReportSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = TenantUsageReport
        fields = "__all__"


# --- Serializer para as Estatísticas do Dashboard ---


class DashboardStatsSerializer(serializers.Serializer):
    """
    Serializador para as estatísticas agregadas exibidas no dashboard do super admin.
    CORREÇÃO: Os campos foram alinhados com os dados calculados na DashboardStatsViewSet.
    """

    total_tenants = serializers.IntegerField()
    total_users = serializers.IntegerField()
    total_clientes = serializers.IntegerField()
    total_produtos = serializers.IntegerField()
    total_obras = serializers.IntegerField()
    total_orcamentos = serializers.IntegerField()
    total_a_pagar = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_a_receber = serializers.DecimalField(max_digits=15, decimal_places=2)
    open_alerts = serializers.IntegerField(default=0)
