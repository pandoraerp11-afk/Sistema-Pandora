import os
import shutil

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Executa uma limpeza completa de cache do sistema Pandora"

    def add_arguments(self, parser):
        parser.add_argument(
            "--deep",
            action="store_true",
            help="Executa limpeza profunda incluindo arquivos de log",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Iniciando limpeza de cache do sistema Pandora..."))

        # 1. Limpar cache do Django
        self.stdout.write("1. Limpando cache do Django...")
        try:
            cache.clear()
            self.stdout.write(self.style.SUCCESS("   ✓ Cache do Django limpo"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠ Erro ao limpar cache Django: {e}"))

        # 2. Limpar sessões expiradas
        self.stdout.write("2. Limpando sessões expiradas...")
        try:
            call_command("clearsessions")
            self.stdout.write(self.style.SUCCESS("   ✓ Sessões expiradas removidas"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠ Erro ao limpar sessões: {e}"))

        # 3. Limpar arquivos Python compilados (.pyc)
        self.stdout.write("3. Limpando arquivos Python compilados...")
        try:
            call_command("clean_pyc")
            self.stdout.write(self.style.SUCCESS("   ✓ Arquivos .pyc removidos"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠ Erro ao limpar .pyc: {e}"))

        # 4. Limpar cache de templates (se houver)
        self.stdout.write("4. Limpando cache de templates...")
        try:
            # Tentar limpar cache específico de templates se existir
            if hasattr(cache, "delete_many"):
                # Buscar todas as chaves que começam com 'template.'
                template_keys = [key for key in cache._cache if key.startswith("template.")]
                if template_keys:
                    cache.delete_many(template_keys)
            self.stdout.write(self.style.SUCCESS("   ✓ Cache de templates limpo"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠ Erro ao limpar cache de templates: {e}"))

        # 5. Regenerar arquivos estáticos
        self.stdout.write("5. Regenerando arquivos estáticos...")
        try:
            call_command("collectstatic", "--noinput", "--clear")
            self.stdout.write(self.style.SUCCESS("   ✓ Arquivos estáticos regenerados"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠ Erro ao coletar estáticos: {e}"))

        # 6. Limpeza profunda (opcional)
        if options["deep"]:
            self.stdout.write("6. Executando limpeza profunda...")

            # Limpar logs antigos (se existirem)
            logs_dirs = ["logs", "log", "tmp", "temp"]
            for log_dir in logs_dirs:
                log_path = os.path.join(settings.BASE_DIR, log_dir)
                if os.path.exists(log_path):
                    try:
                        for filename in os.listdir(log_path):
                            if filename.endswith((".log", ".tmp")):
                                os.remove(os.path.join(log_path, filename))
                        self.stdout.write(self.style.SUCCESS(f"   ✓ Logs limpos em {log_dir}"))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"   ⚠ Erro ao limpar {log_dir}: {e}"))

            # Limpar diretório de media temporário (se existir)
            temp_media_path = os.path.join(settings.MEDIA_ROOT, "temp")
            if os.path.exists(temp_media_path):
                try:
                    shutil.rmtree(temp_media_path)
                    os.makedirs(temp_media_path, exist_ok=True)
                    self.stdout.write(self.style.SUCCESS("   ✓ Arquivos de media temporários limpos"))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"   ⚠ Erro ao limpar media temporário: {e}"))

        # 7. Verificar saúde do sistema após limpeza
        self.stdout.write("7. Verificando integridade do sistema...")
        try:
            call_command("check")
            self.stdout.write(self.style.SUCCESS("   ✓ Sistema verificado - sem problemas detectados"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠ Verificação encontrou problemas: {e}"))

        self.stdout.write(self.style.SUCCESS("\n🎉 Limpeza de cache concluída com sucesso!"))
        self.stdout.write(
            self.style.HTTP_INFO("💡 Para limpeza profunda, execute: python manage.py clear_system_cache --deep")
        )
