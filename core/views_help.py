from django.views.generic import TemplateView


class AjudaView(TemplateView):
    template_name = "ajuda/ajuda_home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["topicos"] = [
            {"titulo": "Navegação", "itens": ["Dashboard", "Módulos", "Busca rápida"]},
            {
                "titulo": "Usuários & Permissões",
                "itens": ["Perfis", "Permissões personalizadas", "Acesso multi-empresa"],
            },
            {"titulo": "Operações", "itens": ["Cadastros", "Estoque", "Financeiro", "Obras"]},
            {"titulo": "Assistência Inteligente", "itens": ["Assistente Web", "AI Auditor", "Sugestões contextuais"]},
        ]
        return ctx
