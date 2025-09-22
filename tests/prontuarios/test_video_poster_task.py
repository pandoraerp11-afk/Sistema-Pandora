from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from clientes.models import Cliente, PessoaFisica
from core.models import CustomUser, Tenant
from prontuarios.models import FotoEvolucao
from prontuarios.tasks import extrair_video_poster, validar_video


class TestVideoPosterTask(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant Teste", subdomain="tenant-teste")
        self.user = CustomUser.objects.create_user(username="u", password="p")
        self.cliente = Cliente.objects.create(tenant=self.tenant, tipo="PF", status="active")
        self.pf = PessoaFisica.objects.create(
            cliente=self.cliente,
            nome_completo="Cliente Video",
            cpf="98765432100",
            data_nascimento=timezone.now().date(),
            sexo="M",
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @mock.patch("shutil.which", return_value="ffprobe")
    @mock.patch("subprocess.check_output")
    def test_validar_video_sem_video(self, m_out, m_which):
        # Cria foto sem vídeo
        foto = FotoEvolucao.objects.create(
            tenant=self.tenant,
            cliente=self.cliente,
            titulo="SemVideo",
            tipo_foto="GERAL",
            momento="ACOMPANHAMENTO",
            area_fotografada="Geral",
            imagem=SimpleUploadedFile("img.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
            data_foto=timezone.now(),
            visivel_cliente=True,
        )
        res = validar_video(foto.id)
        self.assertFalse(res["ok"])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @mock.patch("shutil.which", side_effect=lambda name: "ffprobe" if name == "ffprobe" else None)
    def test_extrair_poster_quando_ffmpeg_indisponivel(self, m_which):
        # Cria foto com vídeo fictício curto (não será processado sem ffmpeg)
        video_file = SimpleUploadedFile("video.mp4", b"FAKE", content_type="video/mp4")
        foto = FotoEvolucao.objects.create(
            tenant=self.tenant,
            cliente=self.cliente,
            titulo="ComVideo",
            tipo_foto="GERAL",
            momento="ACOMPANHAMENTO",
            area_fotografada="Geral",
            imagem=SimpleUploadedFile("img2.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
            video=video_file,
            data_foto=timezone.now(),
            visivel_cliente=True,
        )
        ok = extrair_video_poster(foto.id)
        self.assertFalse(ok)
