# Skills integradas ao sistema Pandora

import logging

from django.apps import apps
from django.db.models import Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


class PandoraSkills:
    """Conjunto de skills específicas para interagir com o sistema Pandora ERP"""

    def __init__(self, user, speaker, memory):
        self.user = user
        self.speaker = speaker
        self.memory = memory

    def consultar_funcionario(self, entities):
        """Consulta informações sobre funcionários"""
        try:
            Funcionario = apps.get_model("funcionarios", "Funcionario")

            nome = entities.get("nome")
            cpf = entities.get("cpf")

            funcionarios = Funcionario.objects.filter(ativo=True)

            if nome:
                funcionarios = funcionarios.filter(Q(nome__icontains=nome) | Q(sobrenome__icontains=nome))
            elif cpf:
                funcionarios = funcionarios.filter(cpf=cpf)

            if funcionarios.exists():
                if funcionarios.count() == 1:
                    func = funcionarios.first()
                    response = f"Encontrei o funcionário {func.nome} {func.sobrenome}, "
                    response += f"cargo: {func.cargo}, "
                    response += f"departamento: {func.departamento}, "
                    response += f"ativo desde {func.data_admissao.strftime('%d/%m/%Y')}"
                else:
                    response = f"Encontrei {funcionarios.count()} funcionários. "
                    for func in funcionarios[:3]:  # Limita a 3 resultados
                        response += f"{func.nome} {func.sobrenome} ({func.cargo}), "
                    if funcionarios.count() > 3:
                        response += "e outros..."
            else:
                response = "Não encontrei funcionários com esses critérios."

            self.speaker.speak(response)
            return {"status": "success", "message": response}

        except Exception as e:
            logger.error(f"Erro ao consultar funcionário: {e}")
            response = "Desculpe, houve um erro ao consultar os funcionários."
            self.speaker.speak(response)
            return {"status": "error", "message": str(e)}

    def consultar_cliente(self, entities):
        """Consulta informações sobre clientes"""
        try:
            Cliente = apps.get_model("clientes", "Cliente")

            nome = entities.get("nome")

            clientes = Cliente.objects.filter(ativo=True)

            if nome:
                clientes = clientes.filter(nome__icontains=nome)

            if clientes.exists():
                if clientes.count() == 1:
                    cliente = clientes.first()
                    response = f"Cliente: {cliente.nome}, "
                    response += f"CNPJ: {cliente.cnpj}, "
                    response += f"telefone: {cliente.telefone}"
                else:
                    response = f"Encontrei {clientes.count()} clientes. "
                    for cliente in clientes[:3]:
                        response += f"{cliente.nome}, "
                    if clientes.count() > 3:
                        response += "e outros..."
            else:
                response = "Não encontrei clientes com esses critérios."

            self.speaker.speak(response)
            return {"status": "success", "message": response}

        except Exception as e:
            logger.error(f"Erro ao consultar cliente: {e}")
            response = "Desculpe, houve um erro ao consultar os clientes."
            self.speaker.speak(response)
            return {"status": "error", "message": str(e)}

    def consultar_obra(self, entities):
        """Consulta informações sobre obras"""
        try:
            Obra = apps.get_model("obras", "Obra")

            obras = Obra.objects.filter(ativo=True)
            numero = entities.get("numero")

            if numero:
                obras = obras.filter(numero=numero)

            if obras.exists():
                if obras.count() == 1:
                    obra = obras.first()
                    response = f"Obra {obra.numero}: {obra.nome}, "
                    response += f"endereço: {obra.endereco}, "
                    response += f"status: {obra.status}, "
                    response += f"cliente: {obra.cliente.nome if obra.cliente else 'Não informado'}"
                else:
                    response = f"Encontrei {obras.count()} obras ativas. "
                    for obra in obras[:3]:
                        response += f"Obra {obra.numero} ({obra.nome}), "
                    if obras.count() > 3:
                        response += "e outras..."
            else:
                response = "Não encontrei obras com esses critérios."

            self.speaker.speak(response)
            return {"status": "success", "message": response}

        except Exception as e:
            logger.error(f"Erro ao consultar obra: {e}")
            response = "Desculpe, houve um erro ao consultar as obras."
            self.speaker.speak(response)
            return {"status": "error", "message": str(e)}

    def consultar_estoque(self, entities):
        """Consulta informações sobre estoque"""
        try:
            Produto = apps.get_model("produtos", "Produto")
            apps.get_model("estoque", "MovimentacaoEstoque")

            produto_nome = entities.get("produto")

            if produto_nome:
                produtos = Produto.objects.filter(nome__icontains=produto_nome, ativo=True)
                if produtos.exists():
                    response = "Produtos encontrados: "
                    for produto in produtos[:3]:
                        # Aqui você pode implementar lógica para calcular estoque atual
                        response += f"{produto.nome} (Código: {produto.codigo}), "
                else:
                    response = f"Não encontrei produtos com o nome '{produto_nome}'."
            else:
                # Relatório geral de estoque
                produtos_count = Produto.objects.filter(ativo=True).count()
                response = f"Temos {produtos_count} produtos cadastrados no sistema."

            self.speaker.speak(response)
            return {"status": "success", "message": response}

        except Exception as e:
            logger.error(f"Erro ao consultar estoque: {e}")
            response = "Desculpe, houve um erro ao consultar o estoque."
            self.speaker.speak(response)
            return {"status": "error", "message": str(e)}

    def consultar_financeiro(self, entities):
        """Consulta informações financeiras"""
        try:
            Receita = apps.get_model("financeiro", "Receita")
            Despesa = apps.get_model("financeiro", "Despesa")

            hoje = timezone.now().date()
            mes_atual = hoje.replace(day=1)

            receitas_mes = (
                Receita.objects.filter(data__gte=mes_atual, data__lte=hoje).aggregate(total=Sum("valor"))["total"] or 0
            )

            despesas_mes = (
                Despesa.objects.filter(data__gte=mes_atual, data__lte=hoje).aggregate(total=Sum("valor"))["total"] or 0
            )

            saldo = receitas_mes - despesas_mes

            response = "Resumo financeiro do mês: "
            response += f"Receitas: R$ {receitas_mes:,.2f}, "
            response += f"Despesas: R$ {despesas_mes:,.2f}, "
            response += f"Saldo: R$ {saldo:,.2f}"

            self.speaker.speak(response)
            return {"status": "success", "message": response}

        except Exception as e:
            logger.error(f"Erro ao consultar financeiro: {e}")
            response = "Desculpe, houve um erro ao consultar as informações financeiras."
            self.speaker.speak(response)
            return {"status": "error", "message": str(e)}

    def gerar_relatorio(self, entities):
        """Gera relatórios do sistema"""
        try:
            tipo = entities.get("tipo", "geral")

            if tipo == "vendas":
                response = "Relatório de vendas será gerado e enviado para seu email."
            elif tipo == "financeiro":
                response = "Relatório financeiro será gerado e enviado para seu email."
            elif tipo == "funcionarios":
                response = "Relatório de funcionários será gerado e enviado para seu email."
            else:
                response = "Relatório geral será gerado e enviado para seu email."

            # Aqui você pode implementar a lógica real de geração de relatórios

            self.speaker.speak(response)
            return {"status": "success", "message": response}

        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            response = "Desculpe, houve um erro ao gerar o relatório."
            self.speaker.speak(response)
            return {"status": "error", "message": str(e)}

    def abrir_dashboard(self, entities):
        """Fornece informações sobre o dashboard"""
        try:
            response = "O dashboard principal está disponível no menu. "
            response += "Você pode acessar as informações de vendas, financeiro, "
            response += "funcionários e obras em tempo real."

            self.speaker.speak(response)
            return {"status": "success", "message": response, "action": "redirect", "url": "/admin/"}

        except Exception as e:
            logger.error(f"Erro ao abrir dashboard: {e}")
            response = "Desculpe, houve um erro ao acessar o dashboard."
            self.speaker.speak(response)
            return {"status": "error", "message": str(e)}

    def help(self, entities):
        """Fornece ajuda sobre as funcionalidades disponíveis"""
        response = "Posso ajudar você com: "
        response += "consultar funcionários, clientes e obras, "
        response += "verificar estoque e informações financeiras, "
        response += "gerar relatórios, "
        response += "abrir o dashboard, "
        response += "lembrar informações pessoais, "
        response += "e muito mais. O que você gostaria de fazer?"

        self.speaker.speak(response)
        return {"status": "success", "message": response}
