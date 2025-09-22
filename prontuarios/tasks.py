"""
Tarefas assíncronas para o módulo de prontuários.
Este arquivo define tarefas que podem ser executadas em background usando Celery ou similar.
"""

# Funções legadas gerar_relatorio_paciente/backup_dados_paciente removidas com Paciente.
import contextlib
import json
import logging
import os
from datetime import datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from prometheus_client import Counter, Gauge, Summary

from .models import Atendimento, FotoEvolucao

# Métricas
TASK_SUCCESS = Counter("pandora_task_success_total", "Total de tasks Celery bem-sucedidas", ["task"])
TASK_FAILURE = Counter("pandora_task_failure_total", "Total de tasks Celery com falha", ["task"])
VIDEO_TRANSCODE = Counter("pandora_video_transcodes_total", "Transcodificações de vídeo", ["profile"])
VIDEO_VALIDATION_FAILURE = Counter("pandora_video_validation_failure_total", "Falhas de validação de vídeo", ["motivo"])
VIDEO_VALIDATION_SUCCESS = Counter("pandora_video_validation_success_total", "Validações de vídeo OK")

# Métricas adicionais (latência e concorrência)
EXECUTION_TIME = Summary("pandora_task_execution_seconds", "Tempo de execução de tasks", ["task"])
INFLIGHT = Gauge("pandora_task_inflight", "Tasks em execução", ["task"])

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def gerar_variacao_webp(self, foto_id):
    """Gera variação WEBP para a imagem principal (se aplicável)."""
    from time import perf_counter

    start = perf_counter()
    INFLIGHT.labels("gerar_variacao_webp").inc()
    try:
        foto = FotoEvolucao.objects.get(id=foto_id)
        if not foto.imagem or not foto.imagem.name.lower().endswith((".jpg", ".jpeg", ".png")):
            return False
        from io import BytesIO

        from PIL import Image

        foto.imagem.seek(0)
        img = Image.open(foto.imagem)
        webp_io = BytesIO()
        img.save(webp_io, format="WEBP", quality=80, method=6)
        from django.core.files.base import ContentFile

        webp_name = foto.imagem.name.rsplit(".", 1)[0] + ".webp"
        if not foto.imagem_webp:
            foto.imagem_webp.save(webp_name, ContentFile(webp_io.getvalue()), save=True)
        TASK_SUCCESS.labels("gerar_variacao_webp").inc()
        return True
    except Exception as e:
        logger.error(f"Erro gerar WEBP foto {foto_id}: {e}")
        TASK_FAILURE.labels("gerar_variacao_webp").inc()
        return False
    finally:
        EXECUTION_TIME.labels("gerar_variacao_webp").observe(perf_counter() - start)
        INFLIGHT.labels("gerar_variacao_webp").dec()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def gerar_thumbnail_foto(self, foto_id):
    """Gera thumbnail JPEG para a foto caso ainda não exista."""
    from time import perf_counter

    start = perf_counter()
    INFLIGHT.labels("gerar_thumbnail_foto").inc()
    try:
        from io import BytesIO

        from django.core.files.base import ContentFile
        from PIL import Image

        foto = FotoEvolucao.objects.get(id=foto_id)
        if not foto.imagem or foto.imagem_thumbnail:
            return False
        THUMB_SIZE = (600, 600)
        foto.imagem.seek(0)
        img = Image.open(foto.imagem)
        img.thumbnail(THUMB_SIZE)
        thumb_io = BytesIO()
        img.save(thumb_io, format="JPEG", quality=80)
        thumb_name = f"thumb_{foto.imagem.name.split('/')[-1]}"
        foto.imagem_thumbnail.save(thumb_name, ContentFile(thumb_io.getvalue()), save=True)
        TASK_SUCCESS.labels("gerar_thumbnail_foto").inc()
        return True
    except Exception as e:
        logger.error(f"Erro gerar thumbnail foto {foto_id}: {e}")
        TASK_FAILURE.labels("gerar_thumbnail_foto").inc()
        return False
    finally:
        EXECUTION_TIME.labels("gerar_thumbnail_foto").observe(perf_counter() - start)
        INFLIGHT.labels("gerar_thumbnail_foto").dec()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def extrair_video_poster(self, foto_id):
    """Extrai frame (poster) de vídeo associado usando ffmpeg (se disponível)."""
    from time import perf_counter

    start = perf_counter()
    INFLIGHT.labels("extrair_video_poster").inc()
    try:
        foto = FotoEvolucao.objects.get(id=foto_id)
        if not foto.video or foto.video_poster:
            return False
        # Caminhos
        import os
        import subprocess
        import tempfile

        from django.core.files.base import File

        # Usar ffmpeg se existir no PATH
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = foto.video.path
            output_path = os.path.join(tmpdir, "frame.jpg")
            cmd = ["ffmpeg", "-y", "-i", input_path, "-ss", "00:00:01.000", "-vframes", "1", output_path]
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if os.path.exists(output_path):
                    with open(output_path, "rb") as f:
                        foto.video_poster.save(f"poster_{foto.id}.jpg", File(f), save=True)
                    TASK_SUCCESS.labels("extrair_video_poster").inc()
                    return True
            except Exception as e:
                logger.warning(f"ffmpeg indisponível ou falhou para vídeo {foto.id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Erro extrair poster vídeo foto {foto_id}: {e}")
        TASK_FAILURE.labels("extrair_video_poster").inc()
        return False
    finally:
        EXECUTION_TIME.labels("extrair_video_poster").observe(perf_counter() - start)
        INFLIGHT.labels("extrair_video_poster").dec()


def _ffprobe_metadata(path):
    """Retorna metadados básicos de vídeo usando ffprobe se disponível."""
    import shutil
    import subprocess

    if not shutil.which("ffprobe"):
        return None
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-select_streams", "v:0", path]
    try:
        out = subprocess.check_output(cmd)
        data = json.loads(out.decode("utf-8", "ignore"))
        return data
    except Exception:
        return None


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def validar_video(self, foto_id, max_duracao_seg=60, max_width=1920, max_height=1080):
    """Valida duração e resolução do vídeo; remove se inválido."""
    from time import perf_counter

    start = perf_counter()
    INFLIGHT.labels("validar_video").inc()
    try:
        foto = FotoEvolucao.objects.get(id=foto_id)
        if not foto.video:
            return {"ok": False, "motivo": "sem_video"}
        meta = _ffprobe_metadata(foto.video.path)
        if not meta:
            return {"ok": False, "motivo": "ffprobe_indisponivel"}
        streams = meta.get("streams", [])
        if not streams:
            return {"ok": False, "motivo": "stream_nao_detectada"}
        s = streams[0]
        dur = float(s.get("duration") or meta.get("format", {}).get("duration", 0) or 0)
        w = int(s.get("width") or 0)
        h = int(s.get("height") or 0)
        meta_obj = foto.video_meta or {}
        meta_obj.update({"duracao": dur, "width": w, "height": h})
        if dur > max_duracao_seg or w > max_width or h > max_height:
            # Política: apagar vídeo e poster se excede limites
            foto.video.delete(save=False)
            if foto.video_poster:
                foto.video_poster.delete(save=False)
            meta_obj["validacao"] = "reprovado"
            foto.video_meta = meta_obj
            foto.save(update_fields=["video", "video_poster", "video_meta"])
            logger.warning(f"Vídeo inválido removido foto {foto_id}: dur={dur}s {w}x{h}")
            VIDEO_VALIDATION_FAILURE.labels("limites_excedidos").inc()
            return {"ok": False, "motivo": "limites_excedidos", "duracao": dur, "width": w, "height": h}
        meta_obj["validacao"] = "aprovado"
        foto.video_meta = meta_obj
        foto.save(update_fields=["video_meta"])
        VIDEO_VALIDATION_SUCCESS.inc()
        return {"ok": True, "duracao": dur, "width": w, "height": h}
    except Exception as e:
        logger.error(f"Erro validar vídeo {foto_id}: {e}")
        TASK_FAILURE.labels("validar_video").inc()
        return {"ok": False, "erro": str(e)}
    finally:
        EXECUTION_TIME.labels("validar_video").observe(perf_counter() - start)
        INFLIGHT.labels("validar_video").dec()


TRANSCODIFICACAO_FALHAS_CONSECUTIVAS = 0
TRANSCODIFICACAO_FALHAS_LIMITE = 5


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 1})
def transcodificar_video(self, foto_id, target="h264"):  # target: h264|webm
    """Transcodifica vídeo para perfil padronizado (baixa prioridade)."""
    import os
    import shutil
    import subprocess
    import tempfile
    from time import perf_counter

    start = perf_counter()
    INFLIGHT.labels("transcodificar_video").inc()
    redis_client = None
    try:
        global TRANSCODIFICACAO_FALHAS_CONSECUTIVAS
        # Carregar contador persistido se possível
        try:
            import redis

            if getattr(settings, "REDIS_URL", None):
                redis_client = redis.from_url(settings.REDIS_URL)
                stored = redis_client.get("pandora:transcode_failures")
                if stored is not None:
                    TRANSCODIFICACAO_FALHAS_CONSECUTIVAS = int(stored)
        except Exception:
            pass
        if TRANSCODIFICACAO_FALHAS_CONSECUTIVAS >= TRANSCODIFICACAO_FALHAS_LIMITE:
            logger.warning("Circuit breaker ativo: transcodificação pausada")
            return {"ok": False, "motivo": "circuit_breaker"}
        foto = FotoEvolucao.objects.get(id=foto_id)
        if not foto.video:
            return {"ok": False, "motivo": "sem_video"}
        if not shutil.which("ffmpeg"):
            return {"ok": False, "motivo": "ffmpeg_indisponivel"}
        profile = {
            "h264": {"args": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "96k"]},
            "webm": {"args": ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "35", "-c:a", "libopus", "-b:a", "64k"]},
        }.get(target)
        if not profile:
            return {"ok": False, "motivo": "perfil_invalido"}
        with tempfile.TemporaryDirectory() as tmp:
            outputs = []
            targets = ["h264", "webm"] if target == "h264" else [target]
            for tg in targets:
                prof = {
                    "h264": {
                        "args": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "96k"],
                        "ext": "mp4",
                    },
                    "webm": {
                        "args": ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "35", "-c:a", "libopus", "-b:a", "64k"],
                        "ext": "webm",
                    },
                }[tg]
                out_path = os.path.join(tmp, f"transcoded_{tg}.{prof['ext']}")
                cmd = ["ffmpeg", "-y", "-i", foto.video.path] + prof["args"] + [out_path]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if os.path.exists(out_path):
                    outputs.append((tg, out_path))
            # Decidir substituição: manter original se nenhum output significativamente menor
            orig_size = foto.video.size
            best = None
            for tg, path in outputs:
                size = os.path.getsize(path)
                if size < orig_size * 0.85 and (best is None or size < best[2]):
                    best = (tg, path, size)
            if best:
                from django.core.files.base import File

                tg, path, new_size = best
                with open(path, "rb") as f:
                    foto.video.save(f"vid_{foto.id}.{'mp4' if tg == 'h264' else 'webm'}", File(f), save=True)
                TRANSCODIFICACAO_FALHAS_CONSECUTIVAS = 0
                if redis_client:
                    with contextlib.suppress(Exception):
                        redis_client.set("pandora:transcode_failures", 0, ex=3600)
                VIDEO_TRANSCODE.labels(tg).inc()
                meta = foto.video_meta or {}
                meta["transcodificacao"] = {"perfil": tg, "original_size": orig_size, "novo_size": new_size}
                foto.video_meta = meta
                foto.save(update_fields=["video_meta"])
                TASK_SUCCESS.labels("transcodificar_video").inc()
                return {"ok": True, "perfil": tg, "novo_tamanho": new_size}
            TASK_SUCCESS.labels("transcodificar_video").inc()
            return {"ok": True, "perfil": "mantido", "tamanho": orig_size}
        return {"ok": False, "motivo": "saida_nao_gerada"}
    except Exception as e:
        logger.error(f"Erro transcodificar video {foto_id}: {e}")
        TRANSCODIFICACAO_FALHAS_CONSECUTIVAS += 1
        TASK_FAILURE.labels("transcodificar_video").inc()
        try:
            if redis_client:
                redis_client.set("pandora:transcode_failures", TRANSCODIFICACAO_FALHAS_CONSECUTIVAS, ex=3600)
        except Exception:
            pass
        return {"ok": False, "erro": str(e)}
    finally:
        EXECUTION_TIME.labels("transcodificar_video").observe(perf_counter() - start)
        INFLIGHT.labels("transcodificar_video").dec()


@shared_task(bind=True)
def reprocessar_derivados_foto(self, foto_id, forcar=False):
    """Reprocessa derivados (thumbnail, webp, poster) sob demanda."""
    from time import perf_counter

    start = perf_counter()
    INFLIGHT.labels("reprocessar_derivados_foto").inc()
    try:
        foto = FotoEvolucao.objects.get(id=foto_id)
        if forcar or not foto.imagem_thumbnail:
            gerar_thumbnail_foto.apply_async([foto_id])
        if forcar or not foto.imagem_webp:
            gerar_variacao_webp.apply_async([foto_id])
        if foto.video and (forcar or not foto.video_poster):
            extrair_video_poster.apply_async([foto_id])
        TASK_SUCCESS.labels("reprocessar_derivados_foto").inc()
        return {"ok": True}
    except Exception as e:
        logger.error(f"Erro reprocessar derivados foto {foto_id}: {e}")
        TASK_FAILURE.labels("reprocessar_derivados_foto").inc()
        return {"ok": False, "erro": str(e)}
    finally:
        EXECUTION_TIME.labels("reprocessar_derivados_foto").observe(perf_counter() - start)
        INFLIGHT.labels("reprocessar_derivados_foto").dec()


def enviar_relatorio_mensal(tenant_id, email_destino=None):
    """
    Gera e envia relatório mensal de atendimentos por email.

    Args:
        tenant_id: ID do tenant
        email_destino: Email de destino (opcional)
    """
    try:
        from core.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        # Calcular período do mês anterior
        hoje = timezone.now().date()
        primeiro_dia_mes_anterior = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)
        ultimo_dia_mes_anterior = hoje.replace(day=1) - timedelta(days=1)

        # Buscar dados do mês anterior
        atendimentos = Atendimento.objects.filter(
            cliente__tenant=tenant,
            data_atendimento__date__gte=primeiro_dia_mes_anterior,
            data_atendimento__date__lte=ultimo_dia_mes_anterior,
        )

        clientes_atendidos = atendimentos.values_list("cliente", flat=True).distinct().count()
        procedimentos_realizados = atendimentos.count()

        # Agrupar por serviço (mantém chave antiga no contexto para compatibilidade de template)
        procedimentos_stats = {}
        for atendimento in atendimentos.select_related("servico"):
            proc_nome = getattr(getattr(atendimento, "servico", None), "nome_servico", "Serviço")
            if proc_nome not in procedimentos_stats:
                procedimentos_stats[proc_nome] = 0
            procedimentos_stats[proc_nome] += 1

        # Preparar contexto para o template
        contexto = {
            "tenant": tenant,
            "periodo": f"{primeiro_dia_mes_anterior.strftime('%d/%m/%Y')} a {ultimo_dia_mes_anterior.strftime('%d/%m/%Y')}",
            "total_atendimentos": procedimentos_realizados,
            # Mantém chave antiga para compatibilidade de template
            "total_pacientes": clientes_atendidos,
            "total_clientes": clientes_atendidos,
            "procedimentos_stats": procedimentos_stats,
            "atendimentos_recentes": atendimentos.order_by("-data_atendimento")[:10],
        }

        # Renderizar template do email
        assunto = f"Relatório Mensal - Prontuários {tenant.nome}"
        mensagem = render_to_string("prontuarios/emails/relatorio_mensal.html", contexto)

        # Definir destinatário
        if not email_destino:
            email_destino = tenant.email_contato or settings.DEFAULT_FROM_EMAIL

        # Enviar email
        send_mail(
            assunto, mensagem, settings.DEFAULT_FROM_EMAIL, [email_destino], html_message=mensagem, fail_silently=False
        )

        logger.info(f"Relatório mensal enviado para {email_destino} - Tenant: {tenant.nome}")

    except Exception as e:
        logger.error(f"Erro ao enviar relatório mensal: {str(e)}")
        raise


def limpar_arquivos_temporarios():
    """
    Remove arquivos temporários e backups antigos.
    """
    try:
        # Remover backups com mais de 90 dias
        backup_dir = os.path.join(settings.MEDIA_ROOT, "backups", "prontuarios")
        if os.path.exists(backup_dir):
            data_limite = timezone.now() - timedelta(days=90)

            for filename in os.listdir(backup_dir):
                filepath = os.path.join(backup_dir, filename)
                if os.path.isfile(filepath):
                    # Verificar data de modificação do arquivo
                    data_modificacao = datetime.fromtimestamp(os.path.getmtime(filepath))
                    data_modificacao = timezone.make_aware(data_modificacao)

                    if data_modificacao < data_limite:
                        os.remove(filepath)
                        logger.info(f"Backup removido: {filename}")

        # Remover fotos de evolução órfãs (sem registro no banco)
        fotos_dir = os.path.join(settings.MEDIA_ROOT, "prontuarios", "evolucao")
        if os.path.exists(fotos_dir):
            for root, _dirs, files in os.walk(fotos_dir):
                for file in files:
                    filepath = os.path.join(root, file)
                    # Verificar se existe registro no banco
                    relativo = os.path.relpath(filepath, settings.MEDIA_ROOT)
                    if not FotoEvolucao.objects.filter(imagem=relativo).exists():
                        # Verificar se o arquivo tem mais de 7 dias
                        data_modificacao = datetime.fromtimestamp(os.path.getmtime(filepath))
                        data_modificacao = timezone.make_aware(data_modificacao)

                        if data_modificacao < timezone.now() - timedelta(days=7):
                            os.remove(filepath)
                            logger.info(f"Foto órfã removida: {relativo}")

        logger.info("Limpeza de arquivos temporários concluída")

    except Exception as e:
        logger.error(f"Erro na limpeza de arquivos temporários: {str(e)}")
        raise


def gerar_backup_automatico(tenant_id):
    """Placeholder de backup automático pós-remoção de Paciente.
    Atualmente não gera arquivos; mantido para compatibilidade de chamadas existentes.
    """
    from core.models import Tenant

    try:
        tenant = Tenant.objects.get(id=tenant_id)
        logger.info(f"Backup automático ignorado para {tenant.nome}: funcionalidade de paciente removida.")
        return []
    except Exception as e:
        logger.error(f"Erro ao resolver tenant para backup: {e}")
        return []


@shared_task
def verificar_atendimentos_pendentes():
    """
    Verifica atendimentos que deveriam ter sido realizados e envia notificações.
    """
    try:
        from clientes.models import Cliente
        from notifications.models import Notification

        hoje = timezone.now().date()
        # Clientes sem atendimento há mais de 6 meses
        data_limite = hoje - timedelta(days=180)
        clientes_inativos = Cliente.objects.filter(atendimentos__data_atendimento__lt=data_limite).distinct()

        for cliente in clientes_inativos:
            try:
                Notification.objects.create(
                    tenant=cliente.tenant,
                    title="Cliente Inativo",
                    message=f"Cliente {getattr(cliente, 'nome_display', cliente.id)} não tem atendimento há mais de 6 meses.",
                    notification_type="info",
                    target_users="admin",
                )
            except Exception:
                continue

        logger.info(
            f"Verificação de atendimentos pendentes concluída. {clientes_inativos.count()} clientes inativos encontrados."
        )
        return clientes_inativos.count()
    except Exception as e:
        logger.error(f"Erro na verificação de atendimentos pendentes: {e}")
        return 0


def sincronizar_dados_externos(tenant_id):
    """
    Sincroniza dados com sistemas externos (se aplicável).

    Args:
        tenant_id: ID do tenant
    """
    try:
        from core.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        # Esta função pode ser expandida para integrar com:
        # - Sistemas de agendamento
        # - Sistemas de faturamento
        # - Sistemas de estoque
        # - APIs de laboratórios

        logger.info(f"Sincronização de dados externos iniciada para {tenant.nome}")

        # Placeholder para integrações futuras

        logger.info(f"Sincronização de dados externos concluída para {tenant.nome}")

    except Exception as e:
        logger.error(f"Erro na sincronização de dados externos: {str(e)}")
        raise


@shared_task
def processar_imagens_lote(foto_ids):
    """
    Processa múltiplas imagens em lote para otimização.

    Args:
        foto_ids: Lista de IDs das fotos a serem processadas
    """
    try:
        from .utils import redimensionar_imagem

        fotos = FotoEvolucao.objects.filter(id__in=foto_ids)
        processadas = 0

        for foto in fotos:
            if foto.imagem:
                try:
                    imagem_original = foto.imagem
                    imagem_redimensionada = redimensionar_imagem(imagem_original)

                    if imagem_redimensionada != imagem_original:
                        foto.imagem.save(foto.imagem.name, imagem_redimensionada, save=False)
                        foto.save(update_fields=["imagem"])
                        processadas += 1

                except Exception as e:
                    logger.error(f"Erro ao processar imagem {foto.id}: {str(e)}")

        logger.info(f"Processamento de imagens em lote concluído. {processadas} imagens processadas.")

        return processadas

    except Exception as e:
        logger.error(f"Erro no processamento de imagens em lote: {str(e)}")
        raise


def exportar_dados_cliente(cliente_id, formato="json"):
    """Exporta dados clínicos básicos de um cliente (substitui exportar_dados_paciente)."""
    try:
        from clientes.models import Cliente

        from .utils import gerar_relatorio_cliente

        cliente = Cliente.objects.get(id=cliente_id)
        dados_relatorio = gerar_relatorio_cliente(cliente)

        export_dir = os.path.join(settings.MEDIA_ROOT, "exports", "prontuarios")
        os.makedirs(export_dir, exist_ok=True)

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")

        if formato == "json":
            filename = f"cliente_{cliente_id}_{timestamp}.json"
            filepath = os.path.join(export_dir, filename)
            dados_serializaveis = {
                "cliente": getattr(cliente, "nome_display", str(cliente.id)),
                "estatisticas": {
                    "total_atendimentos": dados_relatorio["total_atendimentos"],
                    "total_fotos": dados_relatorio["total_fotos"],
                },
                "timestamp_exportacao": timezone.now().isoformat(),
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(dados_serializaveis, f, ensure_ascii=False, indent=2)
        else:
            raise ValueError("Formato não suportado ainda")

        logger.info(f"Dados do cliente {cliente_id} exportados para {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Erro na exportação de dados do cliente: {e}")
        raise


# Funções para agendamento de tarefas (usando Celery ou similar)
def agendar_tarefas_periodicas():
    """
    Agenda tarefas periódicas do sistema.
    Esta função deve ser chamada na inicialização do sistema.
    """
    # Exemplo de como agendar tarefas com Celery:
    # from celery import Celery
    # app = Celery('prontuarios')

    # Relatório mensal (todo dia 1º às 08:00)
    # app.conf.beat_schedule['relatorio-mensal'] = {
    #     'task': 'prontuarios.tasks.enviar_relatorio_mensal',
    #     'schedule': crontab(day_of_month=1, hour=8, minute=0),
    # }

    # Limpeza de arquivos (todo domingo às 02:00)
    # app.conf.beat_schedule['limpeza-arquivos'] = {
    #     'task': 'prontuarios.tasks.limpar_arquivos_temporarios',
    #     'schedule': crontab(day_of_week=0, hour=2, minute=0),
    # }

    # Backup automático (todo dia às 03:00)
    # app.conf.beat_schedule['backup-automatico'] = {
    #     'task': 'prontuarios.tasks.gerar_backup_automatico',
    #     'schedule': crontab(hour=3, minute=0),
    # }

    pass


@shared_task
def executar_backup_automatico_tenants():
    """Executa backup automático para todos os tenants caso flag esteja habilitada."""
    if not getattr(settings, "PRONTUARIOS_AUTO_BACKUP_ENABLED", False):
        return 0
    from core.models import Tenant

    total = 0
    for tenant in Tenant.objects.all():
        try:
            gerar_backup_automatico(tenant.id)
            total += 1
        except Exception as e:
            logger.error(f"Erro backup tenant {tenant.id}: {e}")
    return total
