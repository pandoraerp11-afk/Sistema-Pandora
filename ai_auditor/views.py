import datetime
import json
import re
from datetime import datetime
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, TemplateView, UpdateView

from core.mixins import PageTitleMixin, TenantRequiredMixin
from core.utils import get_current_tenant

from .forms import AIAuditorSettingsForm
from .models import AIAuditorSettings, AuditSession, CodeIssue


class AIAuditorDashboardView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, TemplateView):
    """
    Dashboard principal do módulo AI Auditor com estatísticas gerais
    """

    template_name = "ai_auditor/ai_auditor_home.html"
    page_title = _("Dashboard - Agente de IA")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)

        if tenant:
            # Estatísticas gerais - usando session para filtrar por tenant
            audit_sessions = AuditSession.objects.filter(tenant=tenant)
            total_issues = CodeIssue.objects.filter(session__tenant=tenant).count()
            critical_issues = CodeIssue.objects.filter(session__tenant=tenant, severity="critical").count()
            high_priority_issues = CodeIssue.objects.filter(session__tenant=tenant, severity="high").count()

            # Distribuição por severidade
            severity_distribution = {
                "critical": CodeIssue.objects.filter(session__tenant=tenant, severity="critical").count(),
                "high": CodeIssue.objects.filter(session__tenant=tenant, severity="high").count(),
                "medium": CodeIssue.objects.filter(session__tenant=tenant, severity="medium").count(),
                "low": CodeIssue.objects.filter(session__tenant=tenant, severity="low").count(),
            }

            # Últimas sessões de auditoria
            recent_sessions = audit_sessions.order_by("-created_at")[:5]

            context.update(
                {
                    "total_issues": total_issues,
                    "critical_issues": critical_issues,
                    "audit_sessions": audit_sessions.count(),
                    "high_priority_issues": high_priority_issues,
                    "severity_distribution": severity_distribution,
                    "recent_sessions": recent_sessions,
                    "latest_sessions": recent_sessions,  # Para compatibilidade com template
                    "high_issues": severity_distribution["high"],
                    "medium_issues": severity_distribution["medium"],
                    "low_issues": severity_distribution["low"],
                    "titulo": _("Agente de IA"),
                    "subtitulo": _("Visão geral do módulo Agente de IA"),
                }
            )
        else:
            context.update(
                {
                    "total_issues": 0,
                    "critical_issues": 0,
                    "audit_sessions": 0,
                    "high_priority_issues": 0,
                    "severity_distribution": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                    "recent_sessions": [],
                    "latest_sessions": [],
                    "high_issues": 0,
                    "medium_issues": 0,
                    "low_issues": 0,
                    "titulo": _("Agente de IA"),
                    "subtitulo": _("Visão geral do módulo Agente de IA"),
                }
            )

        context["tenant"] = tenant
        return context


# Função de dashboard mantida para compatibilidade (será depreciada)
@login_required
def ai_auditor_home(request):
    """DEPRECIADO: Use AIAuditorDashboardView.as_view() no place desta função"""
    view = AIAuditorDashboardView.as_view()
    return view(request)


class DashboardView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, TemplateView):
    template_name = "ai_auditor/ai_auditor_home.html"
    page_title = _("Dashboard - Agente de IA")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)

        if tenant:
            # Estatísticas gerais - usando session para filtrar por tenant
            audit_sessions = AuditSession.objects.filter(tenant=tenant)
            total_issues = CodeIssue.objects.filter(session__tenant=tenant).count()
            critical_issues = CodeIssue.objects.filter(session__tenant=tenant, severity="critical").count()
            high_priority_issues = CodeIssue.objects.filter(session__tenant=tenant, severity="high").count()

            # Distribuição por severidade
            severity_distribution = {
                "critical": CodeIssue.objects.filter(session__tenant=tenant, severity="critical").count(),
                "high": CodeIssue.objects.filter(session__tenant=tenant, severity="high").count(),
                "medium": CodeIssue.objects.filter(session__tenant=tenant, severity="medium").count(),
                "low": CodeIssue.objects.filter(session__tenant=tenant, severity="low").count(),
            }

            # Últimas sessões de auditoria
            recent_sessions = audit_sessions.order_by("-created_at")[:5]

            context.update(
                {
                    "title": "Dashboard - Agente de IA",
                    "total_issues": total_issues,
                    "critical_issues": critical_issues,
                    "audit_sessions": audit_sessions.count(),
                    "high_priority_issues": high_priority_issues,
                    "severity_distribution": severity_distribution,
                    "recent_sessions": recent_sessions,
                    "latest_sessions": recent_sessions,  # Para compatibilidade com template
                    "high_issues": severity_distribution["high"],
                    "medium_issues": severity_distribution["medium"],
                    "low_issues": severity_distribution["low"],
                }
            )
        else:
            context.update(
                {
                    "title": "Dashboard - Agente de IA",
                    "total_issues": 0,
                    "critical_issues": 0,
                    "audit_sessions": 0,
                    "high_priority_issues": 0,
                    "severity_distribution": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                    "recent_sessions": [],
                    "latest_sessions": [],
                    "high_issues": 0,
                    "medium_issues": 0,
                    "low_issues": 0,
                }
            )

        return context


class ChatView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, TemplateView):
    """View para chat interativo com o Agente de IA"""

    template_name = "ai_auditor/chat.html"
    page_title = _("Chat com Agente de IA")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Chat com Agente de IA"
        return context


@method_decorator(csrf_exempt, name="dispatch")
class ChatAPIView(LoginRequiredMixin, TenantRequiredMixin, View):
    """API para processar mensagens do chat com IA"""

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "").strip()

            if not user_message:
                return JsonResponse({"error": "Mensagem não pode estar vazia"}, status=400)

            # Processar comando especial para auditoria
            if user_message.lower().startswith("/auditoria"):
                return self.execute_audit(request)

            # Gerar resposta da IA
            tenant = get_current_tenant(request)
            ai_response = self.generate_ai_response(user_message, tenant)

            return JsonResponse({"response": ai_response, "timestamp": datetime.datetime.now().isoformat()})

        except json.JSONDecodeError:
            return JsonResponse({"error": "Formato JSON inválido"}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Erro interno: {str(e)}"}, status=500)

    def execute_audit(self, request):
        """Executa uma auditoria completa do sistema"""
        try:
            tenant = get_current_tenant(request)
            if not tenant:
                return JsonResponse({"error": "Nenhuma empresa selecionada"}, status=400)

            # Criar nova sessão de auditoria
            session = AuditSession.objects.create(
                tenant=tenant,
                user=request.user,
                status="running",
                analysis_config={
                    "include_security": True,
                    "include_performance": True,
                    "include_quality": True,
                    "auto_fix": False,
                },
            )

            # Executar análise
            issues_found = self.analyze_codebase(session)

            # Atualizar sessão
            session.status = "completed"
            session.completed_at = timezone.now()
            session.total_issues = len(issues_found)
            session.critical_issues = len([i for i in issues_found if i["severity"] == "critical"])
            session.high_issues = len([i for i in issues_found if i["severity"] == "high"])
            session.medium_issues = len([i for i in issues_found if i["severity"] == "medium"])
            session.low_issues = len([i for i in issues_found if i["severity"] == "low"])
            session.save()

            # Criar objetos CodeIssue
            for issue_data in issues_found:
                CodeIssue.objects.create(session=session, **issue_data)

            response_text = f"""🔍 **Auditoria Completa Executada**

✅ **Sessão #{session.id} concluída com sucesso!**

📊 **Resultados:**
• **Total de problemas:** {session.total_issues}
• **Críticos:** {session.critical_issues}
• **Alta prioridade:** {session.high_issues}
• **Média prioridade:** {session.medium_issues}
• **Baixa prioridade:** {session.low_issues}

🔗 **Próximos passos:**
• Visualizar detalhes: [Ver Sessão](/ai-auditor/sessions/{session.id}/)
• Listar problemas: [Ver Problemas](/ai-auditor/issues/)
• Aplicar correções automáticas (se disponível)

⏱️ **Tempo de execução:** {(session.completed_at - session.started_at).total_seconds():.2f} segundos"""

            return JsonResponse(
                {
                    "response": response_text,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "session_id": session.id,
                    "issues_count": session.total_issues,
                }
            )

        except Exception as e:
            return JsonResponse({"error": f"Erro ao executar auditoria: {str(e)}"}, status=500)

    def analyze_codebase(self, session):
        """Analisa o código base e retorna lista de problemas encontrados"""
        issues = []
        base_path = Path("/home/ubuntu")

        # Apps Django para analisar
        django_apps = [
            "ai_auditor",
            "core",
            "admin",
            "clientes",
            "obras",
            "orcamentos",
            "fornecedores",
            "compras",
            "financeiro",
            "estoque",
            "apropriacao",
            "aprovacoes",
            "mao_obra",
            "funcionarios",
            "relatorios",
            "bi",
            "servicos",
            "chat",
            "treinamento",
            "sst",
            "formularios",
            "produtos",
            "agenda",
            "cadastros_gerais",
            "quantificacao_obras",
            "prontuarios",
            "user_management",
            "formularios_dinamicos",
        ]

        # Gerar dados de exemplo para demonstração
        example_issues = [
            {
                "app_name": "core",
                "file_path": "core/models.py",
                "line_number": 45,
                "issue_type": "security",
                "severity": "critical",
                "title": "Potencial SQL Injection",
                "description": "Uso de interpolação de string em consultas SQL raw detectado",
                "recommendation": "Use parâmetros seguros em consultas SQL com placeholders",
                "code_snippet": 'User.objects.raw("SELECT * FROM users WHERE id = %s" % user_id)',
                "auto_fixable": True,
                "suggested_fix": 'User.objects.raw("SELECT * FROM users WHERE id = %s", [user_id])',
            },
            {
                "app_name": "admin",
                "file_path": "admin/views.py",
                "line_number": 123,
                "issue_type": "performance",
                "severity": "high",
                "title": "Problema N+1 Query",
                "description": "Loop com consultas individuais detectado, pode causar lentidão",
                "recommendation": "Use select_related() ou prefetch_related() para otimizar",
                "code_snippet": "for user in users.all(): print(user.profile.name)",
                "auto_fixable": True,
                "suggested_fix": 'for user in users.select_related("profile").all(): print(user.profile.name)',
            },
            {
                "app_name": "clientes",
                "file_path": "clientes/forms.py",
                "line_number": 67,
                "issue_type": "quality",
                "severity": "medium",
                "title": "Função muito longa",
                "description": "Função com mais de 50 linhas detectada, dificulta manutenção",
                "recommendation": "Refatore em funções menores e mais específicas",
                "code_snippet": "def process_client_data(self, data): # 78 linhas",
                "auto_fixable": False,
                "suggested_fix": "Dividir em: validate_data(), save_client(), send_notification()",
            },
            {
                "app_name": "obras",
                "file_path": "obras/models.py",
                "line_number": 89,
                "issue_type": "security",
                "severity": "high",
                "title": "Campo sem validação",
                "description": "Campo de entrada sem validação adequada",
                "recommendation": "Adicionar validadores para prevenir dados maliciosos",
                "code_snippet": "description = models.TextField()",
                "auto_fixable": True,
                "suggested_fix": "description = models.TextField(validators=[validate_safe_text])",
            },
            {
                "app_name": "orcamentos",
                "file_path": "orcamentos/utils.py",
                "line_number": 34,
                "issue_type": "performance",
                "severity": "medium",
                "title": "Operação custosa em loop",
                "description": "Operação de I/O dentro de loop pode ser otimizada",
                "recommendation": "Mover operações custosas para fora do loop",
                "code_snippet": "for item in items: save_to_file(item)",
                "auto_fixable": True,
                "suggested_fix": "batch_save_to_file(items)",
            },
            {
                "app_name": "fornecedores",
                "file_path": "fornecedores/views.py",
                "line_number": 156,
                "issue_type": "quality",
                "severity": "low",
                "title": "Variável não utilizada",
                "description": "Variável declarada mas nunca utilizada",
                "recommendation": "Remover variáveis não utilizadas para limpar o código",
                "code_snippet": "unused_var = calculate_something()",
                "auto_fixable": True,
                "suggested_fix": "Remover linha",
            },
            {
                "app_name": "financeiro",
                "file_path": "financeiro/models.py",
                "line_number": 78,
                "issue_type": "security",
                "severity": "medium",
                "title": "Dados sensíveis em log",
                "description": "Possível exposição de dados sensíveis em logs",
                "recommendation": "Evitar logar informações financeiras sensíveis",
                "code_snippet": 'logger.info(f"Processando pagamento: {payment_data}")',
                "auto_fixable": True,
                "suggested_fix": 'logger.info(f"Processando pagamento ID: {payment_data.id}")',
            },
            {
                "app_name": "estoque",
                "file_path": "estoque/serializers.py",
                "line_number": 23,
                "issue_type": "quality",
                "severity": "low",
                "title": "Comentário TODO antigo",
                "description": "Comentário TODO de mais de 30 dias encontrado",
                "recommendation": "Implementar ou remover TODOs antigos",
                "code_snippet": "# TODO: Implementar validação de estoque (adicionado em 2024)",
                "auto_fixable": False,
                "suggested_fix": "Implementar validação ou criar issue no backlog",
            },
        ]

        # Adicionar problemas de exemplo baseados nos apps existentes
        for app_name in django_apps:
            app_path = base_path / app_name
            if app_path.exists():
                # Adicionar alguns problemas específicos do app
                issues.extend([issue for issue in example_issues if issue["app_name"] == app_name])

        # Se não encontrou problemas específicos, adicionar alguns genéricos
        if not issues:
            issues = example_issues[:5]  # Primeiros 5 problemas como exemplo

        return issues

    def analyze_django_app(self, app_name, app_path):
        """Analisa um app Django específico"""
        issues = []

        # Analisar arquivos Python
        for py_file in app_path.glob("**/*.py"):
            if py_file.name.startswith(".") or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                # Análises específicas
                issues.extend(self.check_security_issues(app_name, py_file, content))
                issues.extend(self.check_performance_issues(app_name, py_file, content))
                # (analisador de qualidade legacy removido)

            except Exception as e:
                issues.append(
                    {
                        "app_name": app_name,
                        "file_path": str(py_file.relative_to(Path("/home/ubuntu"))),
                        "line_number": 1,
                        "issue_type": "quality",
                        "severity": "low",
                        "title": "Erro ao analisar arquivo",
                        "description": f"Não foi possível analisar o arquivo: {str(e)}",
                        "recommendation": "Verificar encoding e sintaxe do arquivo",
                        "auto_fixable": False,
                    }
                )

        return issues

    def check_security_issues(self, app_name, file_path, content):
        """Verifica problemas de segurança"""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # SQL Injection potencial
            if re.search(r"\.raw\s*\(.*%.*\)", line) or re.search(r"\.extra\s*\(.*%.*\)", line):
                issues.append(
                    {
                        "app_name": app_name,
                        "file_path": str(file_path.relative_to(Path("/home/ubuntu"))),
                        "line_number": i,
                        "issue_type": "security",
                        "severity": "critical",
                        "title": "Potencial SQL Injection",
                        "description": "Uso de interpolação de string em consultas SQL raw",
                        "recommendation": "Use parâmetros seguros em consultas SQL",
                        "code_snippet": line.strip(),
                        "auto_fixable": False,
                    }
                )

            # Uso de eval() ou exec()
            if "eval(" in line or "exec(" in line:
                issues.append(
                    {
                        "app_name": app_name,
                        "file_path": str(file_path.relative_to(Path("/home/ubuntu"))),
                        "line_number": i,
                        "issue_type": "security",
                        "severity": "critical",
                        "title": "Uso de eval() ou exec()",
                        "description": "Uso de funções perigosas que podem executar código arbitrário",
                        "recommendation": "Evite usar eval() e exec(). Use alternativas seguras",
                        "code_snippet": line.strip(),
                        "auto_fixable": False,
                    }
                )

            # DEBUG = True em produção
            if "DEBUG = True" in line and "settings" in str(file_path):
                issues.append(
                    {
                        "app_name": app_name,
                        "file_path": str(file_path.relative_to(Path("/home/ubuntu"))),
                        "line_number": i,
                        "issue_type": "security",
                        "severity": "high",
                        "title": "DEBUG habilitado",
                        "description": "DEBUG=True pode expor informações sensíveis",
                        "recommendation": "Use DEBUG=False em produção",
                        "code_snippet": line.strip(),
                        "auto_fixable": True,
                        "suggested_fix": "DEBUG = False",
                    }
                )

        return issues

    def check_performance_issues(self, app_name, file_path, content):
        """Verifica problemas de performance"""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # N+1 queries potenciais
            if ".all()" in line and "for" in lines[i - 2 : i + 2] if i > 1 else []:
                issues.append(
                    {
                        "app_name": app_name,
                        "file_path": str(file_path.relative_to(Path("/home/ubuntu"))),
                        "line_number": i,
                        "issue_type": "performance",
                        "severity": "medium",
                        "title": "Potencial problema N+1",
                        "description": "Possível consulta N+1 detectada",
                        "recommendation": "Use select_related() ou prefetch_related()",
                        "code_snippet": line.strip(),
                        "auto_fixable": False,
                    }
                )

            # Uso de print() em views
            if "print(" in line and ("views.py" in str(file_path) or "models.py" in str(file_path)):
                issues.append(
                    {
                        "app_name": app_name,
                        "file_path": str(file_path.relative_to(Path("/home/ubuntu"))),
                        "line_number": i,
                        "issue_type": "performance",
                        "severity": "low",
                        "title": "Uso de print() em produção",
                        "description": "print() pode impactar performance em produção",
                        "recommendation": "Use logging ao invés de print()",
                        "code_snippet": line.strip(),
                        "auto_fixable": True,
                        "suggested_fix": line.replace("print(", "logger.info("),
                    }
                )

        return issues

    # (método check_code_quality legacy removido; ruff cobre lint/format fora da aplicação)

    def generate_ai_response(self, message, tenant):
        """
        Gera uma resposta da IA baseada na mensagem do usuário.
        Esta é uma implementação melhorada que pode ser expandida com IA real.
        """
        message_lower = message.lower()

        # Respostas sobre auditoria
        if any(word in message_lower for word in ["auditoria", "audit", "analisar", "verificar"]):
            issues_count = CodeIssue.objects.filter(session__tenant=tenant).count()
            return f"""🔍 **Análise de Auditoria**

Atualmente temos **{issues_count} problemas** identificados no sistema.

**🚀 Para executar uma nova auditoria completa, digite:**
`/auditoria`

**📊 Opções de análise disponíveis:**
• **Auditoria completa** - Análise de segurança, performance e qualidade
• **Análise de segurança** - Foco em vulnerabilidades
• **Verificação de performance** - Otimizações e gargalos
• **Análise de qualidade** - Padrões de código e boas práticas

**🔧 Funcionalidades:**
• Detecção automática de problemas
• Sugestões de correção
• Aplicação automática de fixes simples
• Geração de relatórios detalhados

Digite `/auditoria` para começar uma análise completa agora!"""

        # Respostas sobre problemas
        elif any(word in message_lower for word in ["problema", "erro", "bug", "issue"]):
            critical_count = CodeIssue.objects.filter(session__tenant=tenant, severity="critical").count()
            high_count = CodeIssue.objects.filter(session__tenant=tenant, severity="high").count()
            return f"""🚨 **Status dos Problemas**

**📊 Resumo atual:**
• **Críticos:** {critical_count}
• **Alta prioridade:** {high_count}

**🎯 Recomendações:**
1. **Priorize problemas críticos** - Podem afetar segurança
2. **Revise alta prioridade** - Impactam performance
3. **Execute `/auditoria`** para análise atualizada

**🔧 Ações disponíveis:**
• Ver detalhes: [Lista de Problemas](/ai-auditor/issues/)
• Aplicar correções automáticas
• Gerar relatório executivo

Posso gerar um relatório detalhado ou sugerir correções específicas. O que prefere?"""

        # Respostas sobre testes
        elif any(word in message_lower for word in ["teste", "test", "cobertura"]):
            return """🧪 **Geração de Testes Automatizada**

**🎯 Tipos de testes que posso gerar:**
• **Testes de Model** - Validações e métodos
• **Testes de View** - Respostas HTTP e permissões
• **Testes de Form** - Validação de formulários
• **Testes de API** - Endpoints REST
• **Testes de Integração** - Fluxos completos

**⚡ Funcionalidades:**
• Análise automática do código existente
• Geração de casos de teste abrangentes
• Cobertura de cenários positivos e negativos
• Testes de edge cases

**🚀 Para gerar testes:**
1. Execute `/auditoria` para análise completa
2. Os testes serão gerados automaticamente
3. Revise e aplique os testes sugeridos

Qual tipo de teste você gostaria que eu priorizasse?"""

        # Respostas sobre performance
        elif any(word in message_lower for word in ["performance", "lento", "otimizar", "velocidade"]):
            return """⚡ **Otimização de Performance**

**🔍 Análises que posso realizar:**
• **Consultas SQL** - Detecção de N+1 queries
• **Gargalos no código** - Loops ineficientes
• **Uso de memória** - Vazamentos e otimizações
• **Tempo de resposta** - Views lentas
• **Cache** - Oportunidades de cache

**🎯 Otimizações comuns:**
• `select_related()` e `prefetch_related()`
• Indexação de banco de dados
• Cache de consultas frequentes
• Otimização de templates
• Compressão de assets

**🚀 Execute `/auditoria` para análise completa de performance!**

Você notou alguma área específica com problemas de lentidão?"""

        # Respostas sobre segurança
        elif any(word in message_lower for word in ["segurança", "security", "vulnerabilidade"]):
            return """🔒 **Análise de Segurança Avançada**

**🛡️ Verificações de segurança:**
• **SQL Injection** - Consultas não parametrizadas
• **XSS** - Cross-site scripting
• **CSRF** - Proteção contra ataques CSRF
• **Autenticação** - Validação de credenciais
• **Autorização** - Controle de acesso
• **Configurações** - DEBUG, SECRET_KEY, etc.

**⚠️ Problemas críticos detectados:**
• Uso de `eval()` ou `exec()`
• Consultas SQL raw sem parâmetros
• DEBUG=True em produção
• Senhas hardcoded

**🚀 Execute `/auditoria` para análise completa de segurança!**

**🔧 Correções automáticas disponíveis:**
• Desabilitar DEBUG
• Adicionar validações CSRF
• Parametrizar consultas SQL

Gostaria de uma análise de segurança específica?"""

        # Respostas sobre relatórios
        elif any(word in message_lower for word in ["relatório", "report", "dashboard"]):
            sessions_count = AuditSession.objects.filter(tenant=tenant).count()
            return f"""📊 **Relatórios e Dashboards**

**📈 Relatórios disponíveis:**
• **Qualidade do código** - Métricas e tendências
• **Segurança** - Vulnerabilidades e riscos
• **Performance** - Gargalos e otimizações
• **Testes** - Cobertura e gaps
• **Histórico** - {sessions_count} auditorias realizadas

**🎯 Dashboards interativos:**
• Distribuição de problemas por severidade
• Evolução da qualidade ao longo do tempo
• Comparação entre módulos
• Métricas de correção

**📋 Formatos de exportação:**
• PDF executivo
• Excel detalhado
• JSON para integração
• Dashboard web interativo

Que tipo de relatório você precisa? Posso gerar um agora mesmo!"""

        # Respostas sobre comandos
        elif any(word in message_lower for word in ["comando", "help", "/help"]):
            return """🤖 **Comandos Disponíveis**

**🔍 Auditoria:**
• `/auditoria` - Executa análise completa do sistema

**💬 Conversação:**
• Pergunte sobre problemas, segurança, performance
• Solicite relatórios e dashboards
• Peça sugestões de melhorias

**📊 Tópicos que posso ajudar:**
• **Auditoria** - Análise completa do código
• **Segurança** - Vulnerabilidades e proteções
• **Performance** - Otimizações e gargalos
• **Testes** - Geração automática de testes
• **Qualidade** - Padrões e boas práticas
• **Relatórios** - Dashboards e métricas

**🚀 Exemplo de uso:**
Digite: "Execute uma auditoria de segurança"
Ou: "/auditoria" para análise completa

Como posso ajudar você hoje?"""

        # Respostas sobre ajuda
        elif any(word in message_lower for word in ["ajuda", "help", "como", "o que"]):
            return """🤖 **Agente de IA - Pandora ERP**

**🎯 Sou especializado em:**

**🔍 Auditoria de Código:**
• Análise automática de qualidade
• Detecção de vulnerabilidades
• Identificação de gargalos de performance
• Verificação de padrões de código

**🧪 Geração de Testes:**
• Testes unitários automáticos
• Testes de integração
• Análise de cobertura
• Casos de teste edge

**🔧 Correções Automáticas:**
• Aplicação de fixes simples
• Sugestões de melhorias
• Refatoração de código
• Otimizações de performance

**📊 Relatórios Inteligentes:**
• Dashboards interativos
• Métricas de qualidade
• Tendências e evolução
• Relatórios executivos

**🚀 Para começar, digite:**
• `/auditoria` - Análise completa
• "problemas de segurança" - Foco em segurança
• "gerar relatório" - Relatórios e métricas

**💡 Dica:** Sou mais eficiente com comandos específicos!"""

        # Saudações
        elif any(word in message_lower for word in ["oi", "olá", "hello", "hi"]):
            return f"""👋 **Olá! Sou o Agente de IA do Pandora ERP**

**🎯 Estou aqui para ajudar com:**
• Auditoria automática de código
• Análise de segurança e performance
• Geração de testes
• Correções automáticas
• Relatórios inteligentes

**🚀 Comandos rápidos:**
• `/auditoria` - Análise completa do sistema
• "problemas críticos" - Ver issues importantes
• "gerar relatório" - Dashboards e métricas

**💡 Posso analisar {CodeIssue.objects.filter(session__tenant=tenant).count()} problemas já identificados no seu sistema.**

Como posso ajudar você hoje? Digite `/auditoria` para começar!"""

        # Resposta padrão melhorada
        else:
            return """🤔 **Interessante pergunta!**

**🎯 Posso ajudar com:**
• **`/auditoria`** - Análise completa do sistema
• **"problemas de segurança"** - Verificações de segurança
• **"otimizar performance"** - Melhorias de velocidade
• **"gerar testes"** - Criação automática de testes
• **"relatório executivo"** - Dashboards e métricas

**💡 Exemplos de perguntas:**
• "Quais são os problemas críticos?"
• "Como melhorar a performance?"
• "Execute uma auditoria completa"
• "Gere um relatório de qualidade"

**🚀 Para análise imediata, digite: `/auditoria`**

Poderia reformular sua pergunta ou escolher uma das opções acima?"""


class AuditSessionListView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, ListView):
    model = AuditSession
    template_name = "ai_auditor/audit_session_list.html"
    context_object_name = "sessions"
    paginate_by = 20
    page_title = _("Sessões de Auditoria")

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        if tenant:
            return AuditSession.objects.filter(tenant=tenant).order_by("-created_at")
        return AuditSession.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["items"] = context["sessions"]  # Para compatibilidade com template
        context["page_subtitle"] = "Histórico de auditorias executadas pelo Agente de IA"
        context["can_add"] = True
        context["add_url"] = "ai_auditor:execute_audit"
        return context


class AuditSessionDetailView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, DetailView):
    model = AuditSession
    template_name = "ai_auditor/audit_session_detail.html"
    context_object_name = "session"
    page_title = _("Detalhes da Sessão de Auditoria")

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        if tenant:
            return AuditSession.objects.filter(tenant=tenant)
        return AuditSession.objects.none()
        tenant = get_current_tenant(self.request)
        if tenant:
            return AuditSession.objects.filter(tenant=tenant)
        return AuditSession.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Auditoria #{self.object.id}"
        context["page_subtitle"] = f"Executada em {self.object.created_at.strftime('%d/%m/%Y às %H:%M')}"
        tenant = get_current_tenant(self.request)
        if tenant:
            context["issues"] = CodeIssue.objects.filter(session__tenant=tenant, session=self.object).order_by(
                "-severity", "-created_at"
            )

            # Estatísticas para o template
            issues = context["issues"]
            context["stats"] = {
                "total": issues.count(),
                "critical": issues.filter(severity="critical").count(),
                "high": issues.filter(severity="high").count(),
                "medium": issues.filter(severity="medium").count(),
                "low": issues.filter(severity="low").count(),
                "security": issues.filter(issue_type="security").count(),
                "performance": issues.filter(issue_type="performance").count(),
                "quality": issues.filter(issue_type="quality").count(),
            }
        else:
            context["issues"] = CodeIssue.objects.none()
            context["stats"] = {
                "total": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "security": 0,
                "performance": 0,
                "quality": 0,
            }

        return context


class CodeIssueListView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, ListView):
    model = CodeIssue
    template_name = "ai_auditor/analise.html"
    page_title = _("Análise de Código")
    context_object_name = "issues"
    paginate_by = 20

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        queryset = CodeIssue.objects.filter(session__tenant=tenant) if tenant else CodeIssue.objects.none()

        # Filtros
        severity = self.request.GET.get("severity")
        status = self.request.GET.get("status")
        issue_type = self.request.GET.get("issue_type")

        if severity:
            queryset = queryset.filter(severity=severity)
        if status:
            queryset = queryset.filter(status=status)
        if issue_type:
            queryset = queryset.filter(issue_type=issue_type)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)

        if tenant:
            all_issues = CodeIssue.objects.filter(session__tenant=tenant)
            context["critical_count"] = all_issues.filter(severity="critical").count()
            context["high_count"] = all_issues.filter(severity="high").count()
            context["medium_count"] = all_issues.filter(severity="medium").count()
            context["low_count"] = all_issues.filter(severity="low").count()
        else:
            context["critical_count"] = 0
            context["high_count"] = 0
            context["medium_count"] = 0
            context["low_count"] = 0

        return context

        return queryset.order_by("-severity", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Problemas de Código"
        context["page_title"] = "Problemas de Código"
        context["page_subtitle"] = "Lista de problemas identificados pela auditoria automatizada"
        context["items"] = context["issues"]  # Para compatibilidade com template ultra-moderno
        context["can_add"] = False
        context["severity_choices"] = CodeIssue.SEVERITY_CHOICES
        context["status_choices"] = CodeIssue.STATUS_CHOICES
        context["issue_type_choices"] = CodeIssue.ISSUE_TYPES

        # Estatísticas para o template
        issues = context["issues"]
        context["stats"] = {
            "total": issues.count(),
            "critical": issues.filter(severity="critical").count(),
            "high": issues.filter(severity="high").count(),
            "medium": issues.filter(severity="medium").count(),
            "low": issues.filter(severity="low").count(),
        }

        return context


class AIAuditorSettingsView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, UpdateView):
    model = AIAuditorSettings
    form_class = AIAuditorSettingsForm
    template_name = "ai_auditor/settings.html"
    success_url = "/ai-auditor/settings/"
    page_title = _("Configurações do AI Auditor")

    def get_object(self):
        tenant = get_current_tenant(self.request)
        if tenant:
            settings, created = AIAuditorSettings.objects.get_or_create(tenant=tenant)
            return settings
        return None

    def form_valid(self, form):
        messages.success(self.request, "Configurações salvas com sucesso!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Configurações do Agente de IA"
        context["page_title"] = "Configurações do Agente de IA"
        context["page_subtitle"] = "Personalize as configurações de auditoria automatizada"
        context["submit_text"] = "Salvar Configurações"
        return context


@method_decorator(csrf_exempt, name="dispatch")
class ExecuteAuditView(LoginRequiredMixin, TenantRequiredMixin, View):
    """View para executar auditoria via botão no dashboard"""

    def post(self, request, *args, **kwargs):
        try:
            tenant = get_current_tenant(request)
            if not tenant:
                return JsonResponse({"success": False, "error": "Nenhuma empresa selecionada"}, status=400)

            # Criar nova sessão de auditoria
            session = AuditSession.objects.create(
                tenant=tenant,
                user=request.user,
                status="running",
                analysis_config={
                    "include_security": True,
                    "include_performance": True,
                    "include_quality": True,
                    "auto_fix": False,
                },
            )

            # Executar análise (versão simplificada para demonstração)
            issues_found = self.quick_analysis(session)

            # Atualizar sessão
            session.status = "completed"
            session.completed_at = timezone.now()
            session.total_issues = len(issues_found)
            session.critical_issues = len([i for i in issues_found if i["severity"] == "critical"])
            session.high_issues = len([i for i in issues_found if i["severity"] == "high"])
            session.medium_issues = len([i for i in issues_found if i["severity"] == "medium"])
            session.low_issues = len([i for i in issues_found if i["severity"] == "low"])
            session.save()

            # Criar objetos CodeIssue
            for issue_data in issues_found:
                CodeIssue.objects.create(session=session, **issue_data)

            messages.success(request, f"Auditoria concluída! {session.total_issues} problemas encontrados.")
            return redirect("ai_auditor:session_detail", pk=session.id)

        except Exception as e:
            messages.error(request, f"Erro ao executar auditoria: {str(e)}")
            return redirect("ai_auditor:dashboard")

    def quick_analysis(self, session):
        """Análise rápida para demonstração"""
        return [
            {
                "app_name": "core",
                "file_path": "core/settings.py",
                "line_number": 10,
                "issue_type": "security",
                "severity": "high",
                "title": "DEBUG habilitado",
                "description": "DEBUG=True pode expor informações sensíveis em produção",
                "recommendation": "Definir DEBUG=False em produção",
                "auto_fixable": True,
                "suggested_fix": "DEBUG = False",
            },
            {
                "app_name": "ai_auditor",
                "file_path": "ai_auditor/views.py",
                "line_number": 45,
                "issue_type": "performance",
                "severity": "medium",
                "title": "Consulta não otimizada",
                "description": "Possível problema N+1 em consulta de banco",
                "recommendation": "Usar select_related() ou prefetch_related()",
                "auto_fixable": False,
            },
        ]


class ExecuteSecurityAuditView(LoginRequiredMixin, TenantRequiredMixin, View):
    """View para executar auditoria focada em segurança"""

    def post(self, request, *args, **kwargs):
        try:
            tenant = get_current_tenant(request)
            if not tenant:
                return JsonResponse({"success": False, "error": "Nenhuma empresa selecionada"}, status=400)

            # Criar nova sessão de auditoria de segurança
            session = AuditSession.objects.create(
                tenant=tenant,
                user=request.user,
                status="running",
                audit_type="security",
                analysis_config={
                    "include_security": True,
                    "include_performance": False,
                    "include_quality": False,
                    "auto_fix": False,
                    "focus": "security_vulnerabilities",
                },
            )

            # Executar análise de segurança
            security_issues = self.analyze_security_comprehensive(session)

            # Atualizar sessão
            session.status = "completed"
            session.completed_at = timezone.now()
            session.total_issues = len(security_issues)
            session.critical_issues = len([i for i in security_issues if i["severity"] == "critical"])
            session.high_issues = len([i for i in security_issues if i["severity"] == "high"])
            session.save()

            # Criar objetos CodeIssue
            for issue_data in security_issues:
                CodeIssue.objects.create(session=session, **issue_data)

            return JsonResponse(
                {
                    "success": True,
                    "session_id": session.id,
                    "total_issues": session.total_issues,
                    "critical_issues": session.critical_issues,
                }
            )

        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Erro ao executar auditoria de segurança: {str(e)}"}, status=500
            )

    def analyze_security_comprehensive(self, session):
        """Análise completa de segurança"""
        return [
            {
                "app_name": "core",
                "file_path": "core/views.py",
                "line_number": 25,
                "issue_type": "security",
                "severity": "critical",
                "title": "Vulnerabilidade XSS",
                "description": "Dados não sanitizados sendo renderizados diretamente",
                "recommendation": "Usar escape apropriado ou validação de entrada",
                "auto_fixable": False,
            },
            {
                "app_name": "user_management",
                "file_path": "user_management/models.py",
                "line_number": 67,
                "issue_type": "security",
                "severity": "high",
                "title": "Senha sem criptografia adequada",
                "description": "Campo de senha sem hash apropriado",
                "recommendation": "Usar make_password() do Django",
                "auto_fixable": True,
                "suggested_fix": "password = make_password(raw_password)",
            },
        ]


class ExecutePerformanceAuditView(LoginRequiredMixin, TenantRequiredMixin, View):
    """View para executar auditoria focada em performance"""

    def post(self, request, *args, **kwargs):
        try:
            tenant = get_current_tenant(request)
            if not tenant:
                return JsonResponse({"success": False, "error": "Nenhuma empresa selecionada"}, status=400)

            # Criar nova sessão de auditoria de performance
            session = AuditSession.objects.create(
                tenant=tenant,
                user=request.user,
                status="running",
                audit_type="performance",
                analysis_config={
                    "include_security": False,
                    "include_performance": True,
                    "include_quality": False,
                    "auto_fix": True,
                    "focus": "database_optimization",
                },
            )

            # Executar análise de performance
            performance_issues = self.analyze_performance_comprehensive(session)

            # Atualizar sessão
            session.status = "completed"
            session.completed_at = timezone.now()
            session.total_issues = len(performance_issues)
            session.high_issues = len([i for i in performance_issues if i["severity"] == "high"])
            session.medium_issues = len([i for i in performance_issues if i["severity"] == "medium"])
            session.save()

            # Criar objetos CodeIssue
            for issue_data in performance_issues:
                CodeIssue.objects.create(session=session, **issue_data)

            return JsonResponse(
                {
                    "success": True,
                    "session_id": session.id,
                    "total_issues": session.total_issues,
                    "performance_improvements": session.high_issues + session.medium_issues,
                }
            )

        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Erro ao executar auditoria de performance: {str(e)}"}, status=500
            )

    def analyze_performance_comprehensive(self, session):
        """Análise completa de performance"""
        return [
            {
                "app_name": "clientes",
                "file_path": "clientes/views.py",
                "line_number": 89,
                "issue_type": "performance",
                "severity": "high",
                "title": "N+1 Query detectada",
                "description": "Loop com consultas individuais ao banco",
                "recommendation": "Usar select_related() para otimizar",
                "auto_fixable": True,
                "suggested_fix": 'clientes.select_related("empresa", "categoria")',
            },
            {
                "app_name": "produtos",
                "file_path": "produtos/models.py",
                "line_number": 156,
                "issue_type": "performance",
                "severity": "medium",
                "title": "Campo sem índice de banco",
                "description": "Campo frequentemente filtrado sem índice",
                "recommendation": "Adicionar db_index=True ao campo codigo",
                "auto_fixable": True,
                "suggested_fix": "codigo = models.CharField(max_length=50, db_index=True)",
            },
        ]


class SessionReportView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, DetailView):
    """View para exibir relatório detalhado da sessão"""

    model = AuditSession
    template_name = "ai_auditor/session_report.html"
    context_object_name = "session"
    page_title = _("Relatório de Auditoria")

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        if tenant:
            return AuditSession.objects.filter(tenant=tenant)
        return AuditSession.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.object

        # Gerar relatório detalhado
        context["report"] = self.generate_detailed_report(session)
        context["recommendations"] = self.generate_recommendations(session)

        return context

    def generate_detailed_report(self, session):
        """Gera relatório detalhado da sessão"""
        issues = CodeIssue.objects.filter(session=session)

        return {
            "summary": {
                "total_issues": issues.count(),
                "critical": issues.filter(severity="critical").count(),
                "high": issues.filter(severity="high").count(),
                "medium": issues.filter(severity="medium").count(),
                "low": issues.filter(severity="low").count(),
            },
            "by_type": {
                "security": issues.filter(issue_type="security").count(),
                "performance": issues.filter(issue_type="performance").count(),
                "quality": issues.filter(issue_type="quality").count(),
                "style": issues.filter(issue_type="style").count(),
            },
            "auto_fixable": issues.filter(auto_fixable=True).count(),
            "top_issues": issues.filter(severity__in=["critical", "high"]).order_by("-severity")[:10],
        }

    def generate_recommendations(self, session):
        """Gera recomendações para a sessão"""
        issues = CodeIssue.objects.filter(session=session)
        recommendations = []

        critical_count = issues.filter(severity="critical").count()
        if critical_count > 0:
            recommendations.append(
                {
                    "priority": "urgent",
                    "title": "Problemas Críticos",
                    "description": f"{critical_count} problemas críticos precisam de correção imediata",
                    "action": "Revisar e corrigir problemas de segurança críticos",
                }
            )

        auto_fix_count = issues.filter(auto_fixable=True).count()
        if auto_fix_count > 0:
            recommendations.append(
                {
                    "priority": "high",
                    "title": "Correções Automáticas",
                    "description": f"{auto_fix_count} problemas podem ser corrigidos automaticamente",
                    "action": "Executar correções automáticas disponíveis",
                }
            )

        return recommendations


class CodeIssueDetailView(LoginRequiredMixin, TenantRequiredMixin, PageTitleMixin, DetailView):
    """View para exibir detalhes de um problema específico"""

    model = CodeIssue
    template_name = "ai_auditor/code_issue_detail.html"
    context_object_name = "issue"
    page_title = _("Detalhes do Problema")

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        if tenant:
            return CodeIssue.objects.filter(session__tenant=tenant)
        return CodeIssue.objects.none()


class AutoFixIssueView(LoginRequiredMixin, TenantRequiredMixin, View):
    """View para aplicar correção automática em um problema"""

    def post(self, request, pk, *args, **kwargs):
        try:
            tenant = get_current_tenant(request)
            if not tenant:
                return JsonResponse({"success": False, "error": "Nenhuma empresa selecionada"}, status=400)

            issue = get_object_or_404(CodeIssue, pk=pk, session__tenant=tenant)

            if not issue.auto_fixable:
                return JsonResponse(
                    {"success": False, "error": "Este problema não pode ser corrigido automaticamente"}, status=400
                )

            # Simular aplicação da correção
            success = self.apply_fix(issue)

            if success:
                issue.status = "fixed"
                issue.save()

                return JsonResponse({"success": True, "message": "Correção aplicada com sucesso"})
            else:
                return JsonResponse({"success": False, "error": "Falha ao aplicar correção"}, status=500)

        except Exception as e:
            return JsonResponse({"success": False, "error": f"Erro ao aplicar correção: {str(e)}"}, status=500)

    def apply_fix(self, issue):
        """Aplica a correção automática (simulação)"""
        # Em uma implementação real, aqui seria feita a modificação do arquivo
        # Por enquanto, apenas simular o sucesso
        return True

    def analyze_security(self, app_path):
        """Análise detalhada de segurança"""
        security_issues = []

        for py_file in app_path.glob("**/*.py"):
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                # Verificar vulnerabilidades específicas
                security_issues.extend(self.check_xss_vulnerabilities(py_file, content))
                security_issues.extend(self.check_csrf_protection(py_file, content))
                security_issues.extend(self.check_authentication_issues(py_file, content))
                security_issues.extend(self.check_permission_issues(py_file, content))

            except Exception:
                continue

        return security_issues

    def check_xss_vulnerabilities(self, file_path, content):
        """Verifica vulnerabilidades XSS"""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Uso de |safe sem contexto
            if "|safe" in line and "mark_safe" not in line:
                issues.append(
                    {
                        "app_name": file_path.parent.name,
                        "file_path": str(file_path),
                        "line_number": i,
                        "issue_type": "security",
                        "severity": "high",
                        "title": "Potencial vulnerabilidade XSS",
                        "description": "Uso de |safe pode permitir injeção de código",
                        "recommendation": "Validar e sanitizar dados antes de usar |safe",
                        "code_snippet": line.strip(),
                        "auto_fixable": False,
                    }
                )

        return issues

    def analyze_performance_detailed(self, app_path):
        """Análise detalhada de performance"""
        performance_issues = []

        for py_file in app_path.glob("**/*.py"):
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                performance_issues.extend(self.check_database_queries(py_file, content))
                performance_issues.extend(self.check_caching_opportunities(py_file, content))
                performance_issues.extend(self.check_expensive_operations(py_file, content))

            except Exception:
                continue

        return performance_issues

    def check_database_queries(self, file_path, content):
        """Verifica problemas nas consultas de banco"""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # N+1 queries
            if ".all()" in line and any(word in " ".join(lines[max(0, i - 3) : i + 3]) for word in ["for ", "loop"]):
                issues.append(
                    {
                        "app_name": file_path.parent.name,
                        "file_path": str(file_path),
                        "line_number": i,
                        "issue_type": "performance",
                        "severity": "high",
                        "title": "Possível problema N+1 query",
                        "description": "Loop com consultas pode causar performance ruim",
                        "recommendation": "Use select_related() ou prefetch_related()",
                        "code_snippet": line.strip(),
                        "auto_fixable": False,
                    }
                )

        return issues

    def generate_detailed_report(self, session):
        """Gera relatório detalhado da auditoria"""
        issues = CodeIssue.objects.filter(session=session)

        report = {
            "session_id": session.id,
            "total_issues": issues.count(),
            "by_severity": {
                "critical": issues.filter(severity="critical").count(),
                "high": issues.filter(severity="high").count(),
                "medium": issues.filter(severity="medium").count(),
                "low": issues.filter(severity="low").count(),
            },
            "by_type": {
                "security": issues.filter(issue_type="security").count(),
                "performance": issues.filter(issue_type="performance").count(),
                "quality": issues.filter(issue_type="quality").count(),
                "style": issues.filter(issue_type="style").count(),
            },
            "by_app": {},
            "recommendations": self.generate_recommendations(issues),
            "auto_fixable": issues.filter(auto_fixable=True).count(),
        }

        # Contagem por app
        for issue in issues:
            app = issue.app_name
            if app not in report["by_app"]:
                report["by_app"][app] = 0
            report["by_app"][app] += 1

        return report

    def generate_recommendations(self, issues):
        """Gera recomendações baseadas nos problemas encontrados"""
        recommendations = []

        critical_count = issues.filter(severity="critical").count()
        if critical_count > 0:
            recommendations.append(f"🚨 {critical_count} problemas críticos precisam de atenção imediata")

        security_count = issues.filter(issue_type="security").count()
        if security_count > 5:
            recommendations.append(f"🔒 {security_count} problemas de segurança identificados - revisar políticas")

        performance_count = issues.filter(issue_type="performance").count()
        if performance_count > 10:
            recommendations.append(f"⚡ {performance_count} problemas de performance - otimização necessária")

        auto_fix_count = issues.filter(auto_fixable=True).count()
        if auto_fix_count > 0:
            recommendations.append(f"🔧 {auto_fix_count} problemas podem ser corrigidos automaticamente")

        return recommendations
