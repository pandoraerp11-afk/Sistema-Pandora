# Módulo NLP Adaptado para Django: Responsável pelo processamento de linguagem natural

import logging
import re

logger = logging.getLogger(__name__)


class DjangoNLP:
    def __init__(self):
        """Inicializa o processador NLP (atualmente baseado em regras simples)."""
        logger.info("Processador NLP inicializado (modo simples: palavras-chave).")

    def process_command(self, command):
        """Processa o comando do usuário para identificar intenção e entidades.

        Args:
            command (str): O comando de voz ou texto do usuário.

        Returns:
            tuple: (intent, entities) onde intent é a ação desejada (str)
                   e entities é um dicionário com informações extraídas (dict).
                   Retorna (None, {}) se não conseguir identificar.
        """
        if not command:
            return None, {}

        command = command.lower().strip()
        intent = None
        entities = {}

        # --- Regras de Intenção Básicas --- #

        # Sair
        if command in ["sair", "encerrar", "desligar", "tchau", "bye", "exit"]:
            intent = "exit"

        # Obter Hora
        elif any(phrase in command for phrase in ["que horas são", "me diga as horas", "horário atual"]):
            intent = "get_time"

        # Obter Data
        elif any(phrase in command for phrase in ["que dia é hoje", "qual a data", "data atual"]):
            intent = "get_date"

        # Lembrar Informação
        elif command.startswith("lembrar que "):
            match = re.match(r"lembrar que (.*) é (.*)", command)
            if match:
                intent = "remember_info"
                entities["key"] = match.group(1).strip()
                entities["value"] = match.group(2).strip()

        # Buscar Informação na Memória
        elif any(
            command.startswith(phrase) for phrase in ["o que você sabe sobre ", "qual é o meu ", "qual é a minha "]
        ):
            intent = "retrieve_info"
            if command.startswith("o que você sabe sobre "):
                entities["key"] = command[len("o que você sabe sobre ") :].strip()
            elif command.startswith("qual é o meu "):
                entities["key"] = command[len("qual é o meu ") :].strip()
            elif command.startswith("qual é a minha "):
                entities["key"] = command[len("qual é a minha ") :].strip()

        # Sugerir Melhoria
        elif any(phrase in command for phrase in ["sugira uma melhoria", "como você pode melhorar"]):
            intent = "suggest_improvement"

        # --- Integração com Sistema Pandora --- #

        # Consultar Funcionários
        elif any(phrase in command for phrase in ["funcionário", "funcionarios", "colaborador", "empregado"]):
            intent = "consultar_funcionario"
            # Extrai nome se mencionado
            nome_match = re.search(r"(?:funcionário|colaborador|empregado)\s+(\w+)", command)
            if nome_match:
                entities["nome"] = nome_match.group(1)

        # Consultar Clientes
        elif any(phrase in command for phrase in ["cliente", "clientes"]):
            intent = "consultar_cliente"
            nome_match = re.search(r"cliente\s+(\w+)", command)
            if nome_match:
                entities["nome"] = nome_match.group(1)

        # Consultar Obras
        elif any(phrase in command for phrase in ["obra", "obras", "projeto", "projetos"]):
            intent = "consultar_obra"

        # Consultar Estoque
        elif any(phrase in command for phrase in ["estoque", "produto", "produtos", "material", "materiais"]):
            intent = "consultar_estoque"
            produto_match = re.search(r"(?:produto|material)\s+(\w+)", command)
            if produto_match:
                entities["produto"] = produto_match.group(1)

        # Consultar Financeiro
        elif any(phrase in command for phrase in ["financeiro", "receitas", "despesas", "fluxo de caixa"]):
            intent = "consultar_financeiro"

        # Gerar Relatório
        elif any(phrase in command for phrase in ["relatório", "relatorio", "report"]):
            intent = "gerar_relatorio"
            if "vendas" in command:
                entities["tipo"] = "vendas"
            elif "financeiro" in command:
                entities["tipo"] = "financeiro"
            elif "funcionarios" in command:
                entities["tipo"] = "funcionarios"

        # Dashboard
        elif any(phrase in command for phrase in ["dashboard", "painel", "visão geral"]):
            intent = "abrir_dashboard"

        # Buscar Cotação de Ação
        elif any(phrase in command for phrase in ["cotação", "ação", "bolsa"]):
            intent = "get_stock_quote"
            parts = command.split()
            symbol = parts[-1]
            symbol = re.sub(r"[?.,!]*$", "", symbol).upper()
            entities["symbol"] = symbol

        # Ajuda
        elif any(phrase in command for phrase in ["ajuda", "help", "o que você pode fazer"]):
            intent = "help"

        # --- Fallback (Intenção Desconhecida) --- #
        # Se nenhuma regra acima funcionou, a intenção permanece None

        logger.debug(f"Comando processado: '{command}' -> Intenção: {intent} | Entidades: {entities}")
        return intent, entities

    def extract_entities_advanced(self, command, intent):
        """Extração mais avançada de entidades baseada na intenção."""
        entities = {}

        if intent == "consultar_funcionario":
            # Tentar extrair CPF, nome, cargo, etc.
            cpf_match = re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", command)
            if cpf_match:
                entities["cpf"] = cpf_match.group()

        elif intent == "consultar_obra":
            # Tentar extrair número da obra, endereço, etc.
            numero_match = re.search(r"obra\s+(\d+)", command)
            if numero_match:
                entities["numero"] = numero_match.group(1)

        return entities

    def get_similar_intents(self, command):
        """Retorna intenções similares caso a principal não seja reconhecida."""
        similar = []

        if "funcionar" in command:
            similar.append("consultar_funcionario")
        if "client" in command:
            similar.append("consultar_cliente")
        if "project" in command:
            similar.append("consultar_obra")

        return similar
