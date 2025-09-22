# core/serializers.py (VERSÃO CORRIGIDA)

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Department, Role, Tenant, TenantUser

# Obtém o modelo de usuário personalizado ativo no projeto
CustomUser = get_user_model()


class TenantSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo Tenant. Converte os dados da empresa para JSON.
    """

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "subdomain",
            "status",
            "razao_social",
            "cnpj",
            "inscricao_estadual",
            "cpf",
            "rg",
            "enabled_modules",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo CustomUser.
    """

    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "phone",
            "bio",
            "theme_preference",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["date_joined", "last_login"]

    def create(self, validated_data):
        """Cria um novo usuário com senha criptografada."""
        password = validated_data.pop("password", None)
        user = CustomUser.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def update(self, instance, validated_data):
        """Atualiza um usuário, tratando a senha corretamente."""
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save()
        return instance


class RoleSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo Role.
    """

    tenant_name = serializers.ReadOnlyField(source="tenant.name")

    class Meta:
        model = Role
        fields = ["id", "tenant", "tenant_name", "name", "description", "permissions", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class DepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo Department.
    """

    tenant_name = serializers.ReadOnlyField(source="tenant.name")

    class Meta:
        model = Department
        fields = ["id", "tenant", "tenant_name", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class TenantUserSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo de vínculo TenantUser.
    """

    tenant_name = serializers.ReadOnlyField(source="tenant.name")
    user_username = serializers.ReadOnlyField(source="user.username")
    user_email = serializers.ReadOnlyField(source="user.email")
    role_name = serializers.ReadOnlyField(source="role.name", default=None)
    department_name = serializers.ReadOnlyField(source="department.name", default=None)

    # MELHORIA: Adicionando mais detalhes do usuário para facilitar o frontend.
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = TenantUser
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "user",
            "user_username",
            "user_email",
            "user_details",
            "role",
            "role_name",
            "department",
            "department_name",
            "is_tenant_admin",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_at",
            "updated_at",
            "tenant_name",
            "user_username",
            "user_email",
            "role_name",
            "department_name",
            "user_details",
        ]

    def get_user_details(self, obj):
        if not obj.user:
            return None
        return {
            "id": obj.user.id,
            "full_name": obj.user.get_full_name(),
            "is_active": obj.user.is_active,
            "last_login": obj.user.last_login,
        }
