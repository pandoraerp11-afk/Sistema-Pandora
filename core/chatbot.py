#!/usr/bin/env python

"""
Chatbot com IA para o Pandora ERP
Integra funcionalidades de IA para assistência, sugestões e alertas inteligentes
"""

import datetime
import json
import logging
import os

import requests

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("chatbot.log"), logging.StreamHandler()],
)
logger = logging.getLogger("pandora_chatbot")


class PandoraChatbot:
    """
    Implementação do chatbot inteligente para o Pandora ERP
    Suporta múltiplos modelos de IA, incluindo APIs externas e modelos locais
    """

    def __init__(self, config_path: str = "chatbot_config.json"):
        """
        Inicializa o chatbot com configurações

        Args:
            config_path: Caminho para o arquivo de configuração JSON
        """
        self.config = self._load_config(config_path)
        self.model_type = self.config.get("model_type", "openai")
        self.api_key = self.config.get("api_key", "")
        self.model_name = self.config.get("model_name", "gpt-3.5-turbo")
        self.context_window = self.config.get("context_window", 10)
        self.conversation_history = []
        self.system_data = {}

        logger.info(f"Chatbot inicializado com modelo: {self.model_type}/{self.model_name}")

    def _load_config(self, config_path: str) -> dict:
        """
        Carrega configurações do arquivo JSON

        Args:
            config_path: Caminho para o arquivo de configuração

        Returns:
            Dicionário com configurações
        """
        try:
            if os.path.exists(config_path):
                with open(config_path, encoding="utf-8") as f:
                    return json.load(f)
            else:
                logger.warning(f"Arquivo de configuração {config_path} não encontrado. Usando configurações padrão.")
                return {
                    "model_type": "openai",
                    "model_name": "gpt-3.5-turbo",
                    "api_key": "",
                    "context_window": 10,
                    "temperature": 0.7,
                    "max_tokens": 500,
                }
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {str(e)}")
            return {}

    def process_message(self, user_message: str, user_id: str, context: dict = None) -> str:
        """
        Processa uma mensagem do usuário e retorna uma resposta

        Args:
            user_message: Mensagem do usuário
            user_id: Identificador do usuário
            context: Contexto adicional (dados do sistema, etc.)

        Returns:
            Resposta do chatbot
        """
        logger.info(f"Processando mensagem do usuário {user_id}: {user_message[:50]}...")

        # Atualizar contexto do sistema se fornecido
        if context:
            self.system_data.update(context)

        # Adicionar mensagem à história da conversa
        self.conversation_history.append(
            {"role": "user", "content": user_message, "timestamp": datetime.datetime.now().isoformat()}
        )

        # Limitar tamanho do histórico
        if len(self.conversation_history) > self.context_window * 2:
            self.conversation_history = self.conversation_history[-self.context_window * 2 :]

        # Gerar resposta com base no modelo configurado
        response = self._generate_response(user_message, user_id)

        # Adicionar resposta à história da conversa
        self.conversation_history.append(
            {"role": "assistant", "content": response, "timestamp": datetime.datetime.now().isoformat()}
        )

        return response

    def _generate_response(self, user_message: str, user_id: str) -> str:
        """
        Gera uma resposta usando o modelo de IA configurado

        Args:
            user_message: Mensagem do usuário
            user_id: Identificador do usuário

        Returns:
            Resposta gerada pelo modelo
        """
        try:
            if self.model_type == "openai":
                return self._generate_openai_response(user_message)
            elif self.model_type == "local":
                return self._generate_local_response(user_message)
            else:
                logger.error(f"Tipo de modelo não suportado: {self.model_type}")
                return "Desculpe, ocorreu um erro ao processar sua mensagem. Tipo de modelo não suportado."
        except Exception as e:
            logger.error(f"Erro ao gerar resposta: {str(e)}")
            return "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."

    def _generate_openai_response(self, user_message: str) -> str:
        """
        Gera resposta usando a API da OpenAI

        Args:
            user_message: Mensagem do usuário

        Returns:
            Resposta da API
        """
        if not self.api_key:
            logger.error("API key não configurada para OpenAI")
            return "Desculpe, o chatbot não está configurado corretamente. Entre em contato com o administrador do sistema."

        try:
            # Preparar mensagens para a API
            messages = [{"role": "system", "content": self._get_system_prompt()}]

            # Adicionar histórico de conversa
            for item in self.conversation_history[-self.context_window * 2 :]:
                if item["role"] in ["user", "assistant"]:
                    messages.append({"role": item["role"], "content": item["content"]})

            # Fazer requisição à API
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

            data = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.config.get("temperature", 0.7),
                "max_tokens": self.config.get("max_tokens", 500),
            }

            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"Erro na API OpenAI: {response.status_code} - {response.text}")
                return "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."

        except Exception as e:
            logger.error(f"Erro ao gerar resposta com OpenAI: {str(e)}")
            return "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."

    def _generate_local_response(self, user_message: str) -> str:
        """
        Gera resposta usando um modelo local (como GPT4All)

        Args:
            user_message: Mensagem do usuário

        Returns:
            Resposta do modelo local
        """
        try:
            # Implementação para modelo local seria feita aqui
            # Por exemplo, usando a biblioteca GPT4All

            # Exemplo simplificado:
            logger.info("Usando modelo local para gerar resposta")
            return "Esta é uma resposta de placeholder do modelo local. A implementação real usaria GPT4All ou similar."

        except Exception as e:
            logger.error(f"Erro ao gerar resposta com modelo local: {str(e)}")
            return "Desculpe, ocorreu um erro ao processar sua mensagem com o modelo local."

    def _get_system_prompt(self) -> str:
        """
        Gera o prompt do sistema com contexto e instruções

        Returns:
            Prompt do sistema formatado
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

        # Adicionar dados do sistema ao prompt
        system_info = ""
        for key, value in self.system_data.items():
            if isinstance(value, (dict, list)):
                system_info += f"\n- {key}: {json.dumps(value, ensure_ascii=False)}"
            else:
                system_info += f"\n- {key}: {value}"

        return base_prompt + system_info

    def get_suggestions(self, user_id: str, context: dict) -> list[str]:
        """
        Gera sugestões proativas com base no contexto atual

        Args:
            user_id: Identificador do usuário
            context: Contexto atual (tela, dados, etc.)

        Returns:
            Lista de sugestões
        """
        try:
            # Implementação de sugestões baseadas em contexto
            module = context.get("current_module", "")
            context.get("current_screen", "")

            suggestions = []

            # Sugestões específicas por módulo
            if module == "financeiro":
                suggestions.append("Deseja ver um resumo das contas a pagar desta semana?")
                suggestions.append("Posso gerar um relatório de fluxo de caixa para você.")
            elif module == "obras":
                suggestions.append("Quer verificar o cronograma das obras em andamento?")
                suggestions.append("Posso mostrar as obras com prazos próximos do vencimento.")
            elif module == "estoque":
                suggestions.append("Existem itens abaixo do estoque mínimo. Deseja ver a lista?")
                suggestions.append("Posso ajudar a gerar uma ordem de compra para reposição.")

            # Sugestões gerais
            suggestions.append("Como posso ajudar você hoje?")
            suggestions.append("Precisa de ajuda com alguma funcionalidade específica?")

            return suggestions[:3]  # Limitar a 3 sugestões

        except Exception as e:
            logger.error(f"Erro ao gerar sugestões: {str(e)}")
            return ["Como posso ajudar você hoje?"]

    def generate_alerts(self, system_data: dict) -> list[dict]:
        """
        Gera alertas inteligentes com base nos dados do sistema

        Args:
            system_data: Dados atuais do sistema

        Returns:
            Lista de alertas com prioridade e mensagem
        """
        alerts = []

        try:
            # Verificar estoque baixo
            if "estoque" in system_data:
                for item in system_data["estoque"]:
                    if item.get("quantidade", 0) < item.get("minimo", 0):
                        alerts.append(
                            {
                                "priority": "high",
                                "type": "estoque",
                                "message": f"Estoque baixo: {item.get('nome')} - {item.get('quantidade')} unidades",
                                "action": "view_estoque",
                            }
                        )

            # Verificar contas a pagar vencidas
            if "contas_pagar" in system_data:
                hoje = datetime.datetime.now().date()
                for conta in system_data["contas_pagar"]:
                    vencimento = datetime.datetime.fromisoformat(conta.get("vencimento")).date()
                    if vencimento < hoje and not conta.get("pago", False):
                        alerts.append(
                            {
                                "priority": "critical",
                                "type": "financeiro",
                                "message": f"Conta vencida: {conta.get('descricao')} - R$ {conta.get('valor')}",
                                "action": "view_conta",
                            }
                        )

            # Verificar prazos de obras
            if "obras" in system_data:
                hoje = datetime.datetime.now().date()
                for obra in system_data["obras"]:
                    if obra.get("status") == "em_andamento":
                        prazo = datetime.datetime.fromisoformat(obra.get("prazo")).date()
                        dias_restantes = (prazo - hoje).days
                        if dias_restantes <= 7:
                            alerts.append(
                                {
                                    "priority": "medium",
                                    "type": "obras",
                                    "message": f"Prazo próximo: {obra.get('nome')} - {dias_restantes} dias restantes",
                                    "action": "view_obra",
                                }
                            )

            return alerts

        except Exception as e:
            logger.error(f"Erro ao gerar alertas: {str(e)}")
            return []

    def save_conversation(self, user_id: str, filepath: str = None) -> bool:
        """
        Salva o histórico da conversa em arquivo

        Args:
            user_id: Identificador do usuário
            filepath: Caminho para salvar o arquivo (opcional)

        Returns:
            True se salvou com sucesso, False caso contrário
        """
        try:
            if not filepath:
                filepath = f"conversation_{user_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)

            logger.info(f"Conversa salva em {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erro ao salvar conversa: {str(e)}")
            return False

    def load_conversation(self, filepath: str) -> bool:
        """
        Carrega histórico de conversa de um arquivo

        Args:
            filepath: Caminho do arquivo

        Returns:
            True se carregou com sucesso, False caso contrário
        """
        try:
            if os.path.exists(filepath):
                with open(filepath, encoding="utf-8") as f:
                    self.conversation_history = json.load(f)

                logger.info(f"Conversa carregada de {filepath}")
                return True
            else:
                logger.warning(f"Arquivo de conversa não encontrado: {filepath}")
                return False

        except Exception as e:
            logger.error(f"Erro ao carregar conversa: {str(e)}")
            return False

    def clear_conversation(self) -> None:
        """
        Limpa o histórico da conversa atual
        """
        self.conversation_history = []
        logger.info("Histórico de conversa limpo")


# Exemplo de uso
if __name__ == "__main__":
    # Inicializar chatbot
    chatbot = PandoraChatbot()

    # Exemplo de processamento de mensagem
    response = chatbot.process_message(
        "Como faço para criar um novo orçamento?", "user123", {"current_module": "orcamentos"}
    )

    print(f"Resposta: {response}")

    # Exemplo de sugestões
    suggestions = chatbot.get_suggestions("user123", {"current_module": "financeiro", "current_screen": "dashboard"})

    print("Sugestões:")
    for suggestion in suggestions:
        print(f"- {suggestion}")

    # Exemplo de alertas
    system_data = {
        "estoque": [
            {"nome": "Cimento", "quantidade": 5, "minimo": 10},
            {"nome": "Areia", "quantidade": 20, "minimo": 15},
        ],
        "contas_pagar": [
            {"descricao": "Fornecedor XYZ", "valor": 1500.00, "vencimento": "2023-05-25T00:00:00", "pago": False}
        ],
        "obras": [{"nome": "Edifício Alfa", "status": "em_andamento", "prazo": "2023-06-02T00:00:00"}],
    }

    alerts = chatbot.generate_alerts(system_data)

    print("Alertas:")
    for alert in alerts:
        print(f"[{alert['priority']}] {alert['message']}")
