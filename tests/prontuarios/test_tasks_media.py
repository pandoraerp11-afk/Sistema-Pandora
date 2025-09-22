import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from clientes.models import Cliente, PessoaFisica
from core.models import CustomUser, Tenant
from prontuarios.models import FotoEvolucao


class TestTasksMedia(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant X", subdomain="tenant-x")
        self.user = CustomUser.objects.create_user(username="user", password="pwd")
        self.cliente = Cliente.objects.create(tenant=self.tenant, tipo="PF", status="active")
        self.pf = PessoaFisica.objects.create(
            cliente=self.cliente,
            nome_completo="Paciente Teste",
            cpf="12345678901",
            data_nascimento=timezone.now().date(),
            sexo="M",
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_thumbnail_and_webp_tasks_triggered(self):
        # Cria imagem simples em memória
        from PIL import Image

        img = Image.new("RGB", (1200, 800), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        uploaded = SimpleUploadedFile("foto.jpg", buf.read(), content_type="image/jpeg")

        foto = FotoEvolucao.objects.create(
            tenant=self.tenant,
            cliente=self.cliente,
            titulo="Teste",
            tipo_foto="ANTES",
            momento="INICIO_TRATAMENTO",
            area_fotografada="Rosto",
            imagem=uploaded,
            data_foto=timezone.now(),
            visivel_cliente=True,
        )
        # Com CELERY_TASK_ALWAYS_EAGER True, tasks devem ter rodado
        foto.refresh_from_db()
        self.assertTrue(foto.imagem_thumbnail, "Thumbnail não gerada")
        # Hash e tamanho devem estar preenchidos
        self.assertIsNotNone(foto.hash_arquivo)
        self.assertIsNotNone(foto.tamanho_arquivo)
