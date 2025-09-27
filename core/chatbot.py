#!/usr/bin/env python

"""Chatbot com IA para o Pandora ERP.

Integra funcionalidades de IA para assistência, sugestões e alertas inteligentes.
"""

import datetime
import json
import logging
from pathlib import Path
from typing import Any

import requests

# Constantes
HTTP_OK = 200
PRAZO_PROXIMO_DIAS = 7

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("chatbot.log"), logging.StreamHandler()],
)
logger = logging.getLogger("pandora_chatbot")


class PandoraChatbot:
    """Implementação do chatbot inteligente para o Pandora ERP.

    Suporta múltiplos modelos de IA, incluindo APIs externas e modelos locais.
    """

    def __init__(self, config_path: str = "chatbot_config.json") -> None:
        """Inicializa o chatbot com configurações.

        Args:
            config_path: Caminho para o arquivo de configuração JSON.

        """
        self.config = self._load_config(config_path)
        self.model_type = self.config.get("model_type", "openai")
        self.api_key = self.config.get("api_key", "")
        self.model_name = self.config.get("model_name", "gpt-3.5-turbo")
        self.context_window = self.config.get("context_window", 10)
        self.conversation_history: list[dict[str, Any]] = []
        self.system_data: dict[str, Any] = {}

        logger.info("Chatbot inicializado com modelo: %s/%s", self.model_type, self.model_name)

    def _load_config(self, config_path: str) -> dict[str, Any]:
        """Carrega configurações do arquivo JSON.

        Args:
            config_path: Caminho para o arquivo de configuração.

        Returns:
            Dicionário com configurações.

        """
        config_file = Path(config_path)
        try:
            if config_file.exists():
                with config_file.open(encoding="utf-8") as f:
                    return json.load(f)

            logger.warning("Arquivo de configuração %s não encontrado. Usando configs padrão.", config_path)
        except (OSError, json.JSONDecodeError):
            logger.exception("Erro ao carregar configurações.")
            return {}
        else:
            return {
                "model_type": "openai",
                "model_name": "gpt-3.5-turbo",
                "api_key": "",
                "context_window": 10,
                "temperature": 0.7,
                "max_tokens": 500,
            }

    def process_message(self, user_message: str, user_id: str, context: dict[str, Any] | None = None) -> str:
        """Processa uma mensagem do usuário e retorna uma resposta.

        Args:
            user_message: Mensagem do usuário.
            user_id: Identificador do usuário.
            context: Contexto adicional (dados do sistema, etc.).

        Returns:
            Resposta do chatbot.

        """
        logger.info("Processando mensagem do usuário %s: %s...", user_id, user_message[:50])

        if context:
            self.system_data.update(context)

        self.conversation_history.append(
            {
                "role": "user",
                "content": user_message,
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            },
        )

        if len(self.conversation_history) > self.context_window * 2:
            self.conversation_history = self.conversation_history[-self.context_window * 2 :]

        response = self._generate_response(user_message)

        self.conversation_history.append(
            {
                "role": "assistant",
                "content": response,
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            },
        )

        return response

    def _generate_response(self, user_message: str) -> str:
        """Gera uma resposta usando o modelo de IA configurado.

        Args:
            user_message: Mensagem do usuário.

        Returns:
            Resposta gerada pelo modelo.

        """
        try:
            if self.model_type == "openai":
                response = self._generate_openai_response()
            elif self.model_type == "local":
                response = self._generate_local_response(user_message)
            else:
                logger.error("Tipo de modelo não suportado: %s", self.model_type)
                return "Desculpe, ocorreu um erro ao processar sua mensagem. Tipo de modelo não suportado."
        except requests.RequestException:
            logger.exception("Erro ao gerar resposta.")
            return "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."
        else:
            return response

    def _generate_openai_response(self) -> str:
        """Gera resposta usando a API da OpenAI.

        Returns:
            Resposta da API.

        """
        if not self.api_key:
            logger.error("API key não configurada para OpenAI")
            return (
                "Desculpe, o chatbot não está configurado corretamente. "
                "Entre em contato com o administrador do sistema."
            )

        messages = [{"role": "system", "content": self._get_system_prompt()}]
        messages.extend(
            {"role": item["role"], "content": item["content"]}
            for item in self.conversation_history[-self.context_window * 2 :]
            if item["role"] in ["user", "assistant"]
        )

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.config.get("temperature", 0.7),
            "max_tokens": self.config.get("max_tokens", 500),
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=30)

        if response.status_code == HTTP_OK:
            result = response.json()
            return result["choices"][0]["message"]["content"]

        logger.error("Erro na API OpenAI: %s - %s", response.status_code, response.text)
        return "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."

    def _generate_local_response(self, user_message: str) -> str:
        """Gera resposta usando um modelo local (como GPT4All).

        Args:
            user_message: Mensagem do usuário.

        Returns:
            Resposta do modelo local.

        """
        logger.info("Usando modelo local para gerar resposta para: %s", user_message)
        return "Esta é uma resposta de placeholder do modelo local. A implementação real usaria GPT4All ou similar."

    def _get_system_prompt(self) -> str:
        """Gera o prompt do sistema com contexto e instruções.

        Returns:
            Prompt do sistema formatado.

        """
        base_prompt = """
        Você é um assistente virtual do Pandora ERP, um sistema de gestão empresarial completo.
        Seu nome é PandoraBot e você foi projetado para ajudar os usuários com:

        1. Responder perguntas sobre o sistema e suas funcionalidades
        2. Fornecer sugestões baseadas em dados do sistema
        3. Ajudar na navegação e uso dos módulos
        4. Explicar relatórios e métricas
        5. Oferecer dicas de produtividade

        Seja sempre cordial, profissional e objetivo. Quando não souber a resposta,
        indique claramente e sugira entrar em contato com o suporte técnico.

        Informações do sistema:
        """
        system_info = ""
        for key, value in self.system_data.items():
            if isinstance(value, dict | list):
                system_info += f"\n- {key}: {json.dumps(value, ensure_ascii=False)}"
            else:
                system_info += f"\n- {key}: {value}"
        return base_prompt + system_info

    def get_suggestions(self, user_id: str, context: dict[str, Any]) -> list[str]:
        """Gera sugestões proativas com base no contexto atual.

        Args:
            user_id: Identificador do usuário.
            context: Contexto atual (tela, dados, etc.).

        Returns:
            Lista de sugestões.

        """
        try:
            logger.info("Gerando sugestões para o usuário %s", user_id)
            module = context.get("current_module", "")
            suggestions = []

            if module == "financeiro":
                suggestions.extend(
                    [
                        "Deseja ver um resumo das contas a pagar desta semana?",
                        "Posso gerar um relatório de fluxo de caixa para você.",
                    ],
                )
            elif module == "obras":
                suggestions.extend(
                    [
                        "Quer verificar o cronograma das obras em andamento?",
                        "Posso mostrar as obras com prazos próximos do vencimento.",
                    ],
                )
            elif module == "estoque":
                suggestions.extend(
                    [
                        "Existem itens abaixo do estoque mínimo. Deseja ver a lista?",
                        "Posso ajudar a gerar uma ordem de compra para reposição.",
                    ],
                )

            suggestions.extend(
                [
                    "Como posso ajudar você hoje?",
                    "Precisa de ajuda com alguma funcionalidade específica?",
                ],
            )
        except (KeyError, TypeError):
            logger.exception("Erro ao gerar sugestões.")
            return ["Como posso ajudar você hoje?"]
        else:
            return suggestions[:3]

    def _check_estoque_baixo(self, system_data: dict[str, Any], alerts: list[dict[str, Any]]) -> None:
        if "estoque" in system_data:
            alerts.extend(
                {
                    "priority": "high",
                    "type": "estoque",
                    "message": f"Estoque baixo: {item.get('nome')} - {item.get('quantidade')} unidades",
                    "action": "view_estoque",
                }
                for item in system_data["estoque"]
                if item.get("quantidade", 0) < item.get("minimo", 0)
            )

    def _check_contas_vencidas(self, system_data: dict[str, Any], alerts: list[dict[str, Any]]) -> None:
        if "contas_pagar" in system_data:
            hoje = datetime.datetime.now(datetime.UTC).date()
            alerts.extend(
                {
                    "priority": "critical",
                    "type": "financeiro",
                    "message": f"Conta vencida: {conta.get('descricao')} - R$ {conta.get('valor')}",
                    "action": "view_conta",
                }
                for conta in system_data["contas_pagar"]
                if (
                    datetime.datetime.fromisoformat(conta.get("vencimento")).date() < hoje
                    and not conta.get("pago", False)
                )
            )

    def _check_prazos_obras(self, system_data: dict[str, Any], alerts: list[dict[str, Any]]) -> None:
        if "obras" in system_data:
            hoje = datetime.datetime.now(datetime.UTC).date()
            alerts.extend(
                {
                    "priority": "medium",
                    "type": "obras",
                    "message": f"Prazo próximo: {obra.get('nome')} - {dias_restantes} dias restantes",
                    "action": "view_obra",
                }
                for obra in system_data["obras"]
                if obra.get("status") == "em_andamento"
                and (dias_restantes := (datetime.datetime.fromisoformat(obra.get("prazo")).date() - hoje).days)
                <= PRAZO_PROXIMO_DIAS
            )

    def generate_alerts(self, system_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Gera alertas inteligentes com base nos dados do sistema.

        Args:
            system_data: Dados atuais do sistema.

        Returns:
            Lista de alertas com prioridade e mensagem.

        """
        alerts: list[dict[str, Any]] = []
        try:
            self._check_estoque_baixo(system_data, alerts)
            self._check_contas_vencidas(system_data, alerts)
            self._check_prazos_obras(system_data, alerts)
        except (TypeError, KeyError):
            logger.exception("Erro ao gerar alertas.")
            return []
        else:
            return alerts

    def save_conversation(self, user_id: str, filepath: str | None = None) -> bool:
        """Salva o histórico da conversa em arquivo.

        Args:
            user_id: Identificador do usuário.
            filepath: Caminho para salvar o arquivo (opcional).

        Returns:
            True se salvou com sucesso, False caso contrário.

        """
        try:
            if not filepath:
                now = datetime.datetime.now(datetime.UTC)
                filepath = f"conversation_{user_id}_{now.strftime('%Y%m%d_%H%M%S')}.json"

            path = Path(filepath)
            with path.open("w", encoding="utf-8") as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)

        except OSError:
            logger.exception("Erro ao salvar conversa.")
            return False
        else:
            logger.info("Conversa salva em %s", filepath)
            return True

    def load_conversation(self, filepath: str) -> bool:
        """Carrega histórico de conversa de um arquivo.

        Args:
            filepath: Caminho do arquivo.

        Returns:
            True se carregou com sucesso, False caso contrário.

        """
        path = Path(filepath)
        if not path.exists():
            logger.warning("Arquivo de conversa não encontrado: %s", filepath)
            return False
        try:
            with path.open(encoding="utf-8") as f:
                self.conversation_history = json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.exception("Erro ao carregar conversa.")
            return False
        else:
            logger.info("Conversa carregada de %s", filepath)
            return True

    def clear_conversation(self) -> None:
        """Limpa o histórico da conversa atual."""
        self.conversation_history = []
        logger.info("Histórico de conversa limpo")
