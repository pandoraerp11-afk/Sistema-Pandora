import ast
import os
from abc import ABC, abstractmethod
from typing import Any


class BaseAnalyzer(ABC):
    def __init__(self, tenant, session):
        self.tenant = tenant
        self.session = session
        self.issues = []

    @abstractmethod
    def analyze(self, file_path: str, content: str) -> list[dict[str, Any]]:
        pass

    def get_app_files(self, app_name: str) -> list[str]:
        """Retorna lista de arquivos Python do app"""
        app_path = os.path.join(os.getcwd(), app_name)
        python_files = []
        for root, _dirs, files in os.walk(app_path):
            for file in files:
                if file.endswith(".py"):
                    python_files.append(os.path.join(root, file))
        return python_files

    def parse_python_file(self, file_path: str):
        """Parse arquivo Python usando AST"""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            return ast.parse(content), content
        except Exception:
            return None, None
