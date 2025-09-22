from .base import BaseGenerator


class DocGenerator(BaseGenerator):
    def generate_docstring(self, file_path: str, content: str) -> str:
        """Gera docstrings para funções e classes sem documentação"""
        # Implementar lógica para gerar docstrings
        pass

    def generate_api_docs(self, app_name: str) -> str:
        """Gera documentação de API para um app"""
        # Implementar lógica para gerar documentação de API (Swagger/OpenAPI)
        pass

    def generate_model_diagram(self, app_name: str) -> str:
        """Gera diagrama de relacionamento de modelos para um app"""
        # Implementar lógica para gerar diagrama de relacionamento de modelos
        pass
