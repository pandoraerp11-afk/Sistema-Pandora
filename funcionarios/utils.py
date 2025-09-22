# funcionarios/utils.py

import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from dateutil.relativedelta import relativedelta


class CalculadoraINSS:
    """Calculadora para INSS baseada nas faixas de 2024"""

    # Faixas de contribuição INSS 2024
    FAIXAS_INSS = [
        {"min": Decimal("0.00"), "max": Decimal("1412.00"), "aliquota": Decimal("0.075")},
        {"min": Decimal("1412.01"), "max": Decimal("2666.68"), "aliquota": Decimal("0.09")},
        {"min": Decimal("2666.69"), "max": Decimal("4000.03"), "aliquota": Decimal("0.12")},
        {"min": Decimal("4000.04"), "max": Decimal("7786.02"), "aliquota": Decimal("0.14")},
    ]

    TETO_INSS = Decimal("7786.02")

    @classmethod
    def calcular(cls, salario_base: Decimal) -> dict[str, Decimal]:
        """
        Calcula o desconto de INSS baseado no salário

        Args:
            salario_base: Salário base do funcionário

        Returns:
            Dict com valor_desconto, aliquota_efetiva, base_calculo
        """
        if salario_base <= 0:
            return {
                "valor_desconto": Decimal("0.00"),
                "aliquota_efetiva": Decimal("0.00"),
                "base_calculo": Decimal("0.00"),
            }

        base_calculo = min(salario_base, cls.TETO_INSS)
        valor_desconto = Decimal("0.00")

        for faixa in cls.FAIXAS_INSS:
            if base_calculo > faixa["min"]:
                valor_faixa = min(base_calculo, faixa["max"]) - faixa["min"]
                if valor_faixa > 0:
                    valor_desconto += valor_faixa * faixa["aliquota"]

        aliquota_efetiva = (valor_desconto / base_calculo * 100) if base_calculo > 0 else Decimal("0.00")

        return {
            "valor_desconto": valor_desconto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "aliquota_efetiva": aliquota_efetiva.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "base_calculo": base_calculo,
        }


class CalculadoraFGTS:
    """Calculadora para FGTS"""

    ALIQUOTA_FGTS = Decimal("0.08")  # 8%

    @classmethod
    def calcular(cls, salario_base: Decimal) -> dict[str, Decimal]:
        """
        Calcula o FGTS baseado no salário

        Args:
            salario_base: Salário base do funcionário

        Returns:
            Dict com valor_fgts, aliquota, base_calculo
        """
        if salario_base <= 0:
            return {"valor_fgts": Decimal("0.00"), "aliquota": Decimal("0.00"), "base_calculo": Decimal("0.00")}

        valor_fgts = salario_base * cls.ALIQUOTA_FGTS

        return {
            "valor_fgts": valor_fgts.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "aliquota": cls.ALIQUOTA_FGTS * 100,
            "base_calculo": salario_base,
        }


class CalculadoraIRRF:
    """Calculadora para Imposto de Renda Retido na Fonte"""

    # Faixas de IR 2024
    FAIXAS_IRRF = [
        {"min": Decimal("0.00"), "max": Decimal("2112.00"), "aliquota": Decimal("0.00"), "deducao": Decimal("0.00")},
        {
            "min": Decimal("2112.01"),
            "max": Decimal("2826.65"),
            "aliquota": Decimal("0.075"),
            "deducao": Decimal("158.40"),
        },
        {
            "min": Decimal("2826.66"),
            "max": Decimal("3751.05"),
            "aliquota": Decimal("0.15"),
            "deducao": Decimal("370.40"),
        },
        {
            "min": Decimal("3751.06"),
            "max": Decimal("4664.68"),
            "aliquota": Decimal("0.225"),
            "deducao": Decimal("651.73"),
        },
        {
            "min": Decimal("4664.69"),
            "max": Decimal("999999.99"),
            "aliquota": Decimal("0.275"),
            "deducao": Decimal("884.96"),
        },
    ]

    DEDUCAO_DEPENDENTE = Decimal("189.59")  # Por dependente

    @classmethod
    def calcular(
        cls, salario_base: Decimal, numero_dependentes: int = 0, outras_deducoes: Decimal = Decimal("0.00")
    ) -> dict[str, Decimal]:
        """
        Calcula o IRRF baseado no salário e dependentes

        Args:
            salario_base: Salário base do funcionário
            numero_dependentes: Número de dependentes para IR
            outras_deducoes: Outras deduções (plano de saúde, etc.)

        Returns:
            Dict com valor_irrf, aliquota, base_calculo, deducoes_totais
        """
        if salario_base <= 0:
            return {
                "valor_irrf": Decimal("0.00"),
                "aliquota": Decimal("0.00"),
                "base_calculo": Decimal("0.00"),
                "deducoes_totais": Decimal("0.00"),
            }

        # Calcula INSS para deduzir da base
        inss = CalculadoraINSS.calcular(salario_base)

        # Base de cálculo = salário - INSS - outras deduções
        deducao_dependentes = Decimal(numero_dependentes) * cls.DEDUCAO_DEPENDENTE
        deducoes_totais = inss["valor_desconto"] + deducao_dependentes + outras_deducoes
        base_calculo = salario_base - deducoes_totais

        if base_calculo <= 0:
            return {
                "valor_irrf": Decimal("0.00"),
                "aliquota": Decimal("0.00"),
                "base_calculo": base_calculo,
                "deducoes_totais": deducoes_totais,
            }

        # Encontra a faixa correspondente
        faixa_aplicavel = None
        for faixa in cls.FAIXAS_IRRF:
            if faixa["min"] <= base_calculo <= faixa["max"]:
                faixa_aplicavel = faixa
                break

        if not faixa_aplicavel:
            faixa_aplicavel = cls.FAIXAS_IRRF[-1]  # Última faixa

        # Calcula o imposto
        valor_irrf = (base_calculo * faixa_aplicavel["aliquota"]) - faixa_aplicavel["deducao"]
        valor_irrf = max(valor_irrf, Decimal("0.00"))  # Não pode ser negativo

        return {
            "valor_irrf": valor_irrf.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "aliquota": faixa_aplicavel["aliquota"] * 100,
            "base_calculo": base_calculo,
            "deducoes_totais": deducoes_totais,
        }


class CalculadoraFerias:
    """Calculadora para férias"""

    @classmethod
    def calcular_valor_ferias(cls, salario_base: Decimal, dias_ferias: int, dias_abono: int = 0) -> dict[str, Decimal]:
        """
        Calcula o valor das férias

        Args:
            salario_base: Salário base do funcionário
            dias_ferias: Dias de férias gozados
            dias_abono: Dias de abono pecuniário

        Returns:
            Dict com valores calculados
        """
        if salario_base <= 0 or dias_ferias <= 0:
            return {
                "valor_ferias": Decimal("0.00"),
                "valor_abono": Decimal("0.00"),
                "terco_constitucional": Decimal("0.00"),
                "valor_total": Decimal("0.00"),
            }

        # Valor proporcional das férias
        valor_ferias = (salario_base / 30) * dias_ferias

        # 1/3 constitucional sobre as férias
        terco_constitucional = valor_ferias / 3

        # Abono pecuniário (se houver)
        valor_abono = Decimal("0.00")
        if dias_abono > 0:
            valor_abono = (salario_base / 30) * dias_abono
            # 1/3 também sobre o abono
            terco_constitucional += valor_abono / 3

        valor_total = valor_ferias + valor_abono + terco_constitucional

        return {
            "valor_ferias": valor_ferias.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "valor_abono": valor_abono.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "terco_constitucional": terco_constitucional.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "valor_total": valor_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        }

    @classmethod
    def calcular_periodo_aquisitivo(cls, data_admissao: date, data_referencia: date = None) -> dict[str, date]:
        """
        Calcula o período aquisitivo de férias

        Args:
            data_admissao: Data de admissão do funcionário
            data_referencia: Data de referência (padrão: hoje)

        Returns:
            Dict com inicio e fim do período aquisitivo
        """
        if not data_referencia:
            data_referencia = date.today()

        # Calcula quantos anos completos desde a admissão
        anos_completos = (data_referencia - data_admissao).days // 365

        inicio_periodo = data_admissao + relativedelta(years=anos_completos)
        fim_periodo = inicio_periodo + relativedelta(years=1) - timedelta(days=1)

        return {"inicio": inicio_periodo, "fim": fim_periodo}


class CalculadoraDecimoTerceiro:
    """Calculadora para 13º salário"""

    @classmethod
    def calcular_valor_bruto(cls, salario_base: Decimal, meses_trabalhados: int) -> Decimal:
        """
        Calcula o valor bruto do 13º salário

        Args:
            salario_base: Salário base do funcionário
            meses_trabalhados: Meses trabalhados no ano

        Returns:
            Valor bruto do 13º
        """
        if salario_base <= 0 or meses_trabalhados <= 0:
            return Decimal("0.00")

        meses_trabalhados = min(meses_trabalhados, 12)  # Máximo 12 meses
        valor_bruto = (salario_base / 12) * meses_trabalhados

        return valor_bruto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calcular_meses_trabalhados(cls, data_admissao: date, ano_referencia: int, data_demissao: date = None) -> int:
        """
        Calcula quantos meses foram trabalhados no ano

        Args:
            data_admissao: Data de admissão
            ano_referencia: Ano de referência para o 13º
            data_demissao: Data de demissão (se houver)

        Returns:
            Número de meses trabalhados
        """
        inicio_ano = date(ano_referencia, 1, 1)
        fim_ano = date(ano_referencia, 12, 31)

        # Data efetiva de início no ano
        data_inicio = max(data_admissao, inicio_ano)

        # Data efetiva de fim no ano
        data_fim = data_demissao if data_demissao and data_demissao.year == ano_referencia else fim_ano

        if data_inicio > data_fim:
            return 0

        # Calcula meses trabalhados
        meses = 0
        data_atual = data_inicio

        while data_atual <= data_fim:
            # Se trabalhou pelo menos 15 dias no mês, conta o mês
            ultimo_dia_mes = calendar.monthrange(data_atual.year, data_atual.month)[1]
            fim_mes = date(data_atual.year, data_atual.month, ultimo_dia_mes)

            data_fim_mes = min(data_fim, fim_mes)
            dias_trabalhados = (data_fim_mes - data_atual).days + 1

            if dias_trabalhados >= 15:
                meses += 1

            # Próximo mês
            data_atual = fim_mes + timedelta(days=1)

        return min(meses, 12)


class CalculadoraBancoHoras:
    """Calculadora para banco de horas"""

    @classmethod
    def calcular_horas_trabalhadas(cls, registros_ponto: list[dict]) -> dict[str, float]:
        """
        Calcula horas trabalhadas baseado nos registros de ponto

        Args:
            registros_ponto: Lista de registros de ponto do dia

        Returns:
            Dict com horas normais, extras, etc.
        """
        if not registros_ponto:
            return {"horas_normais": 0.0, "horas_extras": 0.0, "total_horas": 0.0}

        # Ordena registros por horário
        registros_ordenados = sorted(registros_ponto, key=lambda x: x["data_hora_registro"])

        total_horas = 0.0
        entrada = None

        for registro in registros_ordenados:
            if registro["tipo_registro"] in ["ENTRADA", "FIM_ALMOCO"]:
                entrada = registro["data_hora_registro"]
            elif registro["tipo_registro"] in ["SAIDA", "INICIO_ALMOCO"] and entrada:
                saida = registro["data_hora_registro"]
                horas = (saida - entrada).total_seconds() / 3600
                total_horas += horas
                entrada = None

        # Considera 8 horas como jornada normal
        jornada_normal = 8.0
        horas_normais = min(total_horas, jornada_normal)
        horas_extras = max(0.0, total_horas - jornada_normal)

        return {
            "horas_normais": round(horas_normais, 2),
            "horas_extras": round(horas_extras, 2),
            "total_horas": round(total_horas, 2),
        }


class CalculadoraMaoObra:
    """Calculadora para custos de mão de obra"""

    @classmethod
    def calcular_custo_total(cls, funcionario, incluir_encargos: bool = True) -> dict[str, Decimal]:
        """
        Calcula o custo total da mão de obra de um funcionário

        Args:
            funcionario: Instância do modelo Funcionario
            incluir_encargos: Se deve incluir encargos sociais

        Returns:
            Dict com breakdown dos custos
        """
        salario_base = funcionario.get_salario_atual()

        if salario_base <= 0:
            return {
                "salario_base": Decimal("0.00"),
                "inss_empresa": Decimal("0.00"),
                "fgts": Decimal("0.00"),
                "ferias": Decimal("0.00"),
                "decimo_terceiro": Decimal("0.00"),
                "outros_encargos": Decimal("0.00"),
                "custo_total_mensal": Decimal("0.00"),
                "custo_total_anual": Decimal("0.00"),
                "custo_hora": Decimal("0.00"),
            }

        # Cálculos básicos
        inss_empresa = salario_base * Decimal("0.20")  # 20% INSS patronal (aproximado)
        fgts = CalculadoraFGTS.calcular(salario_base)["valor_fgts"]

        # Provisões anuais divididas por 12
        ferias_provisao = salario_base * Decimal("1.33") / 12  # Férias + 1/3
        decimo_terceiro_provisao = salario_base / 12

        # Outros encargos (estimativa)
        outros_encargos = salario_base * Decimal("0.05")  # 5% (seguro, medicina do trabalho, etc.)

        custo_total_mensal = (
            salario_base + inss_empresa + fgts + ferias_provisao + decimo_terceiro_provisao + outros_encargos
        )

        custo_total_anual = custo_total_mensal * 12

        # Custo por hora (considerando 220 horas/mês)
        horas_mensais = Decimal("220")
        custo_hora = custo_total_mensal / horas_mensais

        return {
            "salario_base": salario_base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "inss_empresa": inss_empresa.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "fgts": fgts,
            "ferias": ferias_provisao.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "decimo_terceiro": decimo_terceiro_provisao.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "outros_encargos": outros_encargos.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "custo_total_mensal": custo_total_mensal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "custo_total_anual": custo_total_anual.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "custo_hora": custo_hora.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        }

    @classmethod
    def calcular_custo_projeto(cls, funcionarios_horas: list[dict]) -> dict[str, Decimal]:
        """
        Calcula o custo de mão de obra para um projeto

        Args:
            funcionarios_horas: Lista com dicts {'funcionario': obj, 'horas': int}

        Returns:
            Dict com custos do projeto
        """
        custo_total = Decimal("0.00")
        detalhes = []

        for item in funcionarios_horas:
            funcionario = item["funcionario"]
            horas = Decimal(str(item["horas"]))

            custos = cls.calcular_custo_total(funcionario)
            custo_funcionario = custos["custo_hora"] * horas
            custo_total += custo_funcionario

            detalhes.append(
                {
                    "funcionario": funcionario.nome_completo,
                    "horas": horas,
                    "custo_hora": custos["custo_hora"],
                    "custo_total": custo_funcionario,
                }
            )

        return {"custo_total": custo_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "detalhes": detalhes}


class ValidadorRH:
    """Validações específicas para RH"""

    @staticmethod
    def validar_cpf(cpf: str) -> bool:
        """Valida CPF"""
        cpf = "".join(filter(str.isdigit, cpf))

        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False

        # Calcula primeiro dígito
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        digito1 = (soma * 10) % 11
        if digito1 == 10:
            digito1 = 0

        # Calcula segundo dígito
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        digito2 = (soma * 10) % 11
        if digito2 == 10:
            digito2 = 0

        return cpf[-2:] == f"{digito1}{digito2}"

    @staticmethod
    def validar_periodo_ferias(
        data_inicio: date, data_fim: date, periodo_aquisitivo_inicio: date, periodo_aquisitivo_fim: date
    ) -> list[str]:
        """Valida período de férias"""
        erros = []

        if data_fim <= data_inicio:
            erros.append("Data de fim deve ser posterior à data de início")

        dias = (data_fim - data_inicio).days + 1
        if dias > 30:
            erros.append("Período de férias não pode exceder 30 dias")

        # Férias devem ser gozadas até 12 meses após o período aquisitivo
        limite_gozo = periodo_aquisitivo_fim + relativedelta(months=12)
        if data_inicio > limite_gozo:
            erros.append("Férias devem ser gozadas até 12 meses após o período aquisitivo")

        return erros

    @staticmethod
    def validar_idade_minima(data_nascimento: date, data_admissao: date) -> list[str]:
        """Valida idade mínima para trabalho"""
        erros = []

        idade_admissao = (data_admissao - data_nascimento).days // 365

        if idade_admissao < 14:
            erros.append("Idade mínima para trabalho é 14 anos")
        elif idade_admissao < 16:
            erros.append("Entre 14 e 16 anos só é permitido como aprendiz")

        return erros
