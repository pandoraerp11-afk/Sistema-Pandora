# funcionarios/serializers.py

from rest_framework import serializers

from .models import Beneficio, CartaoPonto, DecimoTerceiro, Dependente, Ferias, Funcionario, SalarioHistorico


class DependenteSerializer(serializers.ModelSerializer):
    """Serializer para dependentes"""

    idade = serializers.ReadOnlyField()

    class Meta:
        model = Dependente
        fields = [
            "id",
            "nome_completo",
            "data_nascimento",
            "idade",
            "tipo_dependente",
            "dependente_ir",
            "dependente_salario_familia",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class FuncionarioSerializer(serializers.ModelSerializer):
    """Serializer para funcionários"""

    dependentes = DependenteSerializer(many=True, read_only=True)
    idade = serializers.ReadOnlyField()
    tempo_empresa = serializers.ReadOnlyField()
    salario_atual = serializers.ReadOnlyField(source="get_salario_atual")

    class Meta:
        model = Funcionario
        fields = [
            "id",
            "nome_completo",
            "cpf",
            "rg",
            "data_nascimento",
            "idade",
            "sexo",
            "estado_civil",
            "escolaridade",
            "email_pessoal",
            "telefone_pessoal",
            "telefone_emergencia",
            "contato_emergencia",
            "endereco_cep",
            "endereco_logradouro",
            "endereco_numero",
            "endereco_complemento",
            "endereco_bairro",
            "endereco_cidade",
            "endereco_uf",
            "data_admissao",
            "data_demissao",
            "cargo",
            "departamento",
            "tipo_contrato",
            "jornada_trabalho_horas",
            "salario_base",
            "salario_atual",
            "ativo",
            "banco",
            "agencia",
            "conta",
            "tipo_conta",
            "pis",
            "ctps",
            "titulo_eleitor",
            "reservista",
            "user",
            "observacoes",
            "tempo_empresa",
            "numero_dependentes",
            "dependentes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_cpf(self, value):
        """Valida CPF"""
        from .utils import ValidadorRH

        if value and not ValidadorRH.validar_cpf(value):
            raise serializers.ValidationError("CPF inválido")
        return value

    def validate(self, data):
        """Validações gerais"""
        from .utils import ValidadorRH

        # Valida idade mínima
        if "data_nascimento" in data and "data_admissao" in data:
            erros = ValidadorRH.validar_idade_minima(data["data_nascimento"], data["data_admissao"])
            if erros:
                raise serializers.ValidationError({"data_nascimento": erros})

        return data


class FeriasSerializer(serializers.ModelSerializer):
    """Serializer para férias"""

    funcionario_nome = serializers.CharField(source="funcionario.nome_completo", read_only=True)

    class Meta:
        model = Ferias
        fields = [
            "id",
            "funcionario",
            "funcionario_nome",
            "periodo_aquisitivo_inicio",
            "periodo_aquisitivo_fim",
            "data_inicio",
            "data_fim",
            "dias_gozados",
            "abono_pecuniario",
            "dias_abono",
            "status",
            "data_pagamento",
            "valor_pago",
            "observacoes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        """Validações de férias"""
        from .utils import ValidadorRH

        if all(k in data for k in ["data_inicio", "data_fim", "periodo_aquisitivo_inicio", "periodo_aquisitivo_fim"]):
            erros = ValidadorRH.validar_periodo_ferias(
                data["data_inicio"], data["data_fim"], data["periodo_aquisitivo_inicio"], data["periodo_aquisitivo_fim"]
            )
            if erros:
                raise serializers.ValidationError({"data_inicio": erros})

        # Valida abono pecuniário
        if data.get("abono_pecuniario") and data.get("dias_abono", 0) > 10:
            raise serializers.ValidationError({"dias_abono": "Abono pecuniário não pode exceder 10 dias"})

        return data


class DecimoTerceiroSerializer(serializers.ModelSerializer):
    """Serializer para 13º salário"""

    funcionario_nome = serializers.CharField(source="funcionario.nome_completo", read_only=True)

    class Meta:
        model = DecimoTerceiro
        fields = [
            "id",
            "funcionario",
            "funcionario_nome",
            "ano_referencia",
            "tipo_parcela",
            "meses_trabalhados",
            "valor_bruto",
            "valor_inss",
            "valor_irrf",
            "valor_liquido",
            "data_pagamento",
            "observacoes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CartaoPontoSerializer(serializers.ModelSerializer):
    """Serializer para cartão de ponto"""

    funcionario_nome = serializers.CharField(source="funcionario.nome_completo", read_only=True)
    aprovado_por_nome = serializers.CharField(source="aprovado_por.get_full_name", read_only=True)

    class Meta:
        model = CartaoPonto
        fields = [
            "id",
            "funcionario",
            "funcionario_nome",
            "data_hora_registro",
            "tipo_registro",
            "ip_origem",
            "localizacao",
            "aprovado",
            "aprovado_por",
            "aprovado_por_nome",
            "justificativa",
            "observacoes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "ip_origem", "created_at", "updated_at"]


class BeneficioSerializer(serializers.ModelSerializer):
    """Serializer para benefícios"""

    funcionario_nome = serializers.CharField(source="funcionario.nome_completo", read_only=True)

    class Meta:
        model = Beneficio
        fields = [
            "id",
            "funcionario",
            "funcionario_nome",
            "tipo_beneficio",
            "categoria",
            "valor",
            "data_referencia",
            "recorrente",
            "ativo",
            "observacoes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SalarioHistoricoSerializer(serializers.ModelSerializer):
    """Serializer para histórico salarial"""

    funcionario_nome = serializers.CharField(source="funcionario.nome_completo", read_only=True)
    alterado_por_nome = serializers.CharField(source="alterado_por.get_full_name", read_only=True)

    class Meta:
        model = SalarioHistorico
        fields = [
            "id",
            "funcionario",
            "funcionario_nome",
            "data_vigencia",
            "valor_salario",
            "motivo_alteracao",
            "alterado_por",
            "alterado_por_nome",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
