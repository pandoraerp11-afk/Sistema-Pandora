import datetime
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .core.listener import DjangoListener
from .core.memory import DjangoMemory
from .core.nlp import DjangoNLP
from .core.speaker import DjangoSpeaker
from .models import ConfiguracaoAssistente, ConversaAssistente, MensagemAssistente
from .skills.pandora_skills import PandoraSkills

logger = logging.getLogger(__name__)


@login_required
def assistente_home(request):
    """Página principal do assistente de IA"""
    # Buscar ou criar configuração do usuário
    config, created = ConfiguracaoAssistente.objects.get_or_create(
        usuario=request.user,
        defaults={
            "modo_preferido": "text",
            "auto_speak": True,
            "skills_habilitadas": [
                "consultar_funcionario",
                "consultar_cliente",
                "consultar_obra",
                "consultar_estoque",
                "consultar_financeiro",
                "gerar_relatorio",
                "abrir_dashboard",
                "help",
            ],
        },
    )

    # Buscar conversas recentes
    conversas_recentes = ConversaAssistente.objects.filter(usuario=request.user).order_by("-data_inicio")[:5]

    # Buscar conversa ativa
    conversa_ativa = ConversaAssistente.objects.filter(usuario=request.user, ativa=True).first()

    context = {
        "config": config,
        "conversas_recentes": conversas_recentes,
        "conversa_ativa": conversa_ativa,
    }

    return render(request, "assistente_web/home.html", context)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def processar_comando(request):
    """Processa comandos enviados pelo usuário"""
    try:
        data = json.loads(request.body)
        comando = data.get("comando", "").strip()
        modo = data.get("modo", "text")
        conversa_id = data.get("conversa_id")

        if not comando:
            return JsonResponse({"status": "error", "message": "Comando não pode estar vazio"})

        # Buscar ou criar conversa
        if conversa_id:
            try:
                conversa = ConversaAssistente.objects.get(id=conversa_id, usuario=request.user)
            except ConversaAssistente.DoesNotExist:
                conversa = None
        else:
            conversa = None

        if not conversa:
            conversa = ConversaAssistente.objects.create(
                usuario=request.user, titulo=f"Conversa {timezone.now().strftime('%d/%m/%Y %H:%M')}", modo_entrada=modo
            )

        # Salvar mensagem do usuário
        mensagem_user = MensagemAssistente.objects.create(conversa=conversa, tipo="user", conteudo=comando)

        # Inicializar componentes do assistente
        DjangoListener()
        speaker = DjangoSpeaker()
        nlp = DjangoNLP()
        memory = DjangoMemory(request.user)
        skills = PandoraSkills(request.user, speaker, memory)

        # Processar comando
        intent, entities = nlp.process_command(comando)

        # Atualizar mensagem com intenção detectada
        mensagem_user.intencao = intent
        mensagem_user.entidades = entities
        mensagem_user.processado = True
        mensagem_user.save()

        response_text = ""
        action_data = {}

        # Executar ação baseada na intenção
        if intent == "exit":
            response_text = "Até logo! Encerrando a conversa."
            conversa.ativa = False
            conversa.data_fim = timezone.now()
            conversa.save()

        elif intent == "get_time":
            now = datetime.datetime.now().strftime("%H:%M")
            response_text = f"Agora são {now}."

        elif intent == "get_date":
            today = datetime.datetime.now().strftime("%d de %B de %Y")
            response_text = f"Hoje é {today}."

        elif intent == "remember_info":
            key = entities.get("key")
            value = entities.get("value")
            if key and value:
                if memory.save_info(key, value, source="user"):
                    response_text = f"Ok, lembrei que {key} é {value}."
                else:
                    response_text = "Desculpe, tive um problema ao salvar essa informação."
            else:
                response_text = "Não entendi o que você quer lembrar. Tente dizer 'lembrar que [algo] é [valor]'."

        elif intent == "retrieve_info":
            key = entities.get("key")
            if key:
                info = memory.get_info(key)
                if info:
                    response_text = f"Pelo que sei, {key} é {info['value']}. Salvei isso em {info['timestamp'][:10]}."
                else:
                    response_text = f"Não encontrei nada na memória sobre {key}."
            else:
                response_text = "Não entendi sobre o que você quer saber."

        elif intent == "consultar_funcionario":
            result = skills.consultar_funcionario(entities)
            response_text = result["message"]

        elif intent == "consultar_cliente":
            result = skills.consultar_cliente(entities)
            response_text = result["message"]

        elif intent == "consultar_obra":
            result = skills.consultar_obra(entities)
            response_text = result["message"]

        elif intent == "consultar_estoque":
            result = skills.consultar_estoque(entities)
            response_text = result["message"]

        elif intent == "consultar_financeiro":
            result = skills.consultar_financeiro(entities)
            response_text = result["message"]

        elif intent == "gerar_relatorio":
            result = skills.gerar_relatorio(entities)
            response_text = result["message"]

        elif intent == "abrir_dashboard":
            result = skills.abrir_dashboard(entities)
            response_text = result["message"]
            if result.get("action") == "redirect":
                action_data = {"redirect": result.get("url")}

        elif intent == "help":
            result = skills.help(entities)
            response_text = result["message"]

        else:
            response_text = "Desculpe, não entendi o comando. Digite 'ajuda' para ver o que posso fazer."

        # Salvar resposta do assistente
        mensagem_assistant = MensagemAssistente.objects.create(
            conversa=conversa, tipo="assistant", conteudo=response_text, intencao=intent, entidades=entities
        )

        return JsonResponse(
            {
                "status": "success",
                "response": response_text,
                "intent": intent,
                "entities": entities,
                "conversa_id": conversa.id,
                "mensagem_id": mensagem_assistant.id,
                "action_data": action_data,
            }
        )

    except Exception as e:
        logger.error(f"Erro ao processar comando: {e}")
        return JsonResponse({"status": "error", "message": "Erro interno do servidor"})


@login_required
def nova_conversa(request):
    """Inicia uma nova conversa"""
    # Finalizar conversas ativas
    ConversaAssistente.objects.filter(usuario=request.user, ativa=True).update(ativa=False, data_fim=timezone.now())

    # Criar nova conversa
    conversa = ConversaAssistente.objects.create(
        usuario=request.user, titulo=f"Nova conversa - {timezone.now().strftime('%d/%m/%Y %H:%M')}"
    )

    return JsonResponse({"status": "success", "conversa_id": conversa.id, "message": "Nova conversa iniciada"})


@login_required
def obter_conversa(request, conversa_id):
    """Obtém mensagens de uma conversa específica"""
    try:
        conversa = ConversaAssistente.objects.get(id=conversa_id, usuario=request.user)

        mensagens = []
        for msg in conversa.mensagens.all():
            mensagens.append(
                {
                    "id": msg.id,
                    "tipo": msg.tipo,
                    "conteudo": msg.conteudo,
                    "timestamp": msg.timestamp.isoformat(),
                    "intencao": msg.intencao,
                    "entidades": msg.entidades,
                }
            )

        return JsonResponse(
            {
                "status": "success",
                "conversa": {
                    "id": conversa.id,
                    "titulo": conversa.titulo,
                    "data_inicio": conversa.data_inicio.isoformat(),
                    "ativa": conversa.ativa,
                    "modo_entrada": conversa.modo_entrada,
                },
                "mensagens": mensagens,
            }
        )

    except ConversaAssistente.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Conversa não encontrada"})


@login_required
def configuracoes(request):
    """Página de configurações do assistente"""
    config, created = ConfiguracaoAssistente.objects.get_or_create(usuario=request.user)

    if request.method == "POST":
        config.modo_preferido = request.POST.get("modo_preferido", "text")
        config.auto_speak = request.POST.get("auto_speak") == "on"

        skills_habilitadas = request.POST.getlist("skills_habilitadas")
        config.skills_habilitadas = skills_habilitadas

        config.save()

        messages.success(request, "Configurações salvas com sucesso!")
        return redirect("assistente_web:configuracoes")

    # Lista de skills disponíveis
    skills_disponiveis = [
        ("consultar_funcionario", "Consultar Funcionários"),
        ("consultar_cliente", "Consultar Clientes"),
        ("consultar_obra", "Consultar Obras"),
        ("consultar_estoque", "Consultar Estoque"),
        ("consultar_financeiro", "Consultar Financeiro"),
        ("gerar_relatorio", "Gerar Relatórios"),
        ("abrir_dashboard", "Abrir Dashboard"),
        ("help", "Ajuda"),
    ]

    context = {"config": config, "skills_disponiveis": skills_disponiveis}

    return render(request, "assistente_web/configuracoes.html", context)


@login_required
def historico_conversas(request):
    """Página com histórico de conversas"""
    conversas = ConversaAssistente.objects.filter(usuario=request.user).order_by("-data_inicio")

    context = {"conversas": conversas}

    return render(request, "assistente_web/historico.html", context)
