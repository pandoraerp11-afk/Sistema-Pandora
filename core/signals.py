# core/signals.py

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    ConfiguracaoSistema,
    CustomUser,
    Modulo,
    Tenant,
    TenantPessoaFisica,
    TenantPessoaJuridica,
    UserProfile,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomUser)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Cria um UserProfile toda vez que um novo CustomUser é criado.
    Esta é a solução robusta para garantir que todo usuário tenha um perfil.
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=Tenant)
def create_tenant_related_models(sender, instance, created, **kwargs):
    """
    Cria modelos relacionados após criação do Tenant.
    Versão defensiva com logs e verificações.
    """
    if not created:
        return

    logger.info(f"Signal disparado para Tenant: {instance.name} (tipo: {instance.tipo_pessoa})")

    try:
        if instance.tipo_pessoa == "PF":
            # Criar TenantPessoaFisica
            pf_data = {
                "tenant": instance,
                "nome_completo": instance.name or "Nome não informado",
            }

            # Adicionar campos opcionais apenas se preenchidos
            if instance.cpf:
                pf_data["cpf"] = instance.cpf
            if instance.rg:
                pf_data["rg"] = instance.rg

            logger.info(f"Criando TenantPessoaFisica com dados: {pf_data}")
            TenantPessoaFisica.objects.create(**pf_data)

        elif instance.tipo_pessoa == "PJ":
            # Criar TenantPessoaJuridica
            pj_data = {
                "tenant": instance,
                "razao_social": instance.razao_social or instance.name,
                "nome_fantasia": instance.name,
            }

            # ✅ CORREÇÃO: Adicionar campos opcionais apenas se preenchidos
            if instance.cnpj:
                pj_data["cnpj"] = instance.cnpj
            if instance.inscricao_estadual:
                pj_data["inscricao_estadual"] = instance.inscricao_estadual

            logger.info(f"Criando TenantPessoaJuridica com dados: {pj_data}")
            TenantPessoaJuridica.objects.create(**pj_data)

        # Criar configurações iniciais do sistema
        logger.info(f"Criando ConfiguracaoSistema para tenant: {instance.name}")
        ConfiguracaoSistema.objects.create(tenant=instance)

        # Ativar módulos padrão para novo tenant
        default_modules = Modulo.objects.filter(ativo_por_padrao=True)
        if default_modules.exists():
            logger.info(f"Ativando {default_modules.count()} módulos padrão para tenant: {instance.name}")
            for module in default_modules:
                module.tenants.add(instance)

        logger.info(f"✅ Modelos relacionados criados com sucesso para: {instance.name}")

    except Exception as e:
        logger.error(f"❌ ERRO ao criar modelos relacionados para {instance.name}: {e}")
        logger.error(
            f"   - Dados do tenant: tipo={instance.tipo_pessoa}, cnpj={instance.cnpj}, razao_social={instance.razao_social}"
        )
        # Re-raise para não mascarar o erro
        raise
