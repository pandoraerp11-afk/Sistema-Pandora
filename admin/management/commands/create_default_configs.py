# admin/management/commands/create_default_configs.py

from django.core.management.base import BaseCommand

from admin.models import SystemConfiguration


class Command(BaseCommand):
    help = "Cria as configurações padrão do sistema"

    def handle(self, *args, **options):
        default_configs = [
            # Categoria: Geral
            {
                "key": "SITE_NAME",
                "value": "Pandora ERP",
                "category": "geral",
                "description": "Nome do sistema que aparece nos títulos e e-mails",
                "is_editable": True,
            },
            {
                "key": "MAINTENANCE_MODE",
                "value": False,
                "category": "geral",
                "description": "Chave para colocar o sistema em modo de manutenção",
                "is_editable": True,
            },
            {
                "key": "DEBUG_MODE",
                "value": True,
                "category": "geral",
                "description": "Controle da configuração DEBUG do Django",
                "is_editable": True,
            },
            # Categoria: E-mail (SMTP)
            {
                "key": "EMAIL_HOST",
                "value": "",
                "category": "email",
                "description": "Endereço do servidor SMTP",
                "is_editable": True,
            },
            {
                "key": "EMAIL_PORT",
                "value": 587,
                "category": "email",
                "description": "Porta do servidor SMTP",
                "is_editable": True,
            },
            {
                "key": "EMAIL_HOST_USER",
                "value": "",
                "category": "email",
                "description": "Usuário de autenticação do e-mail",
                "is_editable": True,
            },
            {
                "key": "EMAIL_HOST_PASSWORD",
                "value": "",
                "category": "email",
                "description": "Senha de autenticação do e-mail",
                "is_editable": True,
            },
            {
                "key": "EMAIL_USE_TLS",
                "value": True,
                "category": "email",
                "description": "Se o servidor usa TLS",
                "is_editable": True,
            },
            {
                "key": "DEFAULT_FROM_EMAIL",
                "value": "",
                "category": "email",
                "description": "E-mail remetente padrão",
                "is_editable": True,
            },
            # Categoria: Segurança
            {
                "key": "SESSION_TIMEOUT_MINUTES",
                "value": 60,
                "category": "seguranca",
                "description": "Tempo em minutos para expirar a sessão por inatividade",
                "is_editable": True,
            },
            {
                "key": "MAX_LOGIN_ATTEMPTS",
                "value": 5,
                "category": "seguranca",
                "description": "Número de tentativas de login antes de bloquear um usuário",
                "is_editable": True,
            },
            {
                "key": "PASSWORD_EXPIRATION_DAYS",
                "value": 90,
                "category": "seguranca",
                "description": "Número de dias para a senha expirar",
                "is_editable": True,
            },
            # Categoria: APIs de Terceiros
            {
                "key": "MAPS_API_KEY",
                "value": "",
                "category": "apis",
                "description": "Chave da API do Google Maps para funcionalidades de geolocalização",
                "is_editable": True,
            },
            {
                "key": "WHATSAPP_GATEWAY_URL",
                "value": "",
                "category": "apis",
                "description": "URL do gateway para envio de mensagens via WhatsApp",
                "is_editable": True,
            },
            {
                "key": "WHATSAPP_API_TOKEN",
                "value": "",
                "category": "apis",
                "description": "Token de autenticação para o gateway de WhatsApp",
                "is_editable": True,
            },
            # Categoria: Branding e Aparência
            {
                "key": "FAVICON_URL",
                "value": "",
                "category": "branding",
                "description": "URL para o favicon do sistema",
                "is_editable": True,
            },
            {
                "key": "LOGIN_PAGE_LOGO_URL",
                "value": "",
                "category": "branding",
                "description": "URL para a logo exibida na página de login",
                "is_editable": True,
            },
            {
                "key": "SYSTEM_THEME_COLOR",
                "value": "#007bff",
                "category": "branding",
                "description": "Cor principal do tema para elementos da interface",
                "is_editable": True,
            },
        ]

        created_count = 0
        updated_count = 0

        for config_data in default_configs:
            config, created = SystemConfiguration.objects.get_or_create(key=config_data["key"], defaults=config_data)

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Criada configuração: {config_data['key']}"))
            # Atualiza apenas se não existir ou se a descrição mudou
            elif not config.description or config.description != config_data["description"]:
                config.description = config_data["description"]
                config.category = config_data["category"]
                config.save()
                updated_count += 1
                self.stdout.write(self.style.WARNING(f"Atualizada configuração: {config_data['key']}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Processo concluído! {created_count} configurações criadas, {updated_count} atualizadas."
            )
        )
