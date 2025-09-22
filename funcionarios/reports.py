# funcionarios/reports.py

from datetime import date
from decimal import Decimal
from io import BytesIO

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import CartaoPonto, Ferias, Funcionario
from .utils import CalculadoraBancoHoras, CalculadoraMaoObra


class RelatorioFuncionarios:
    """Gerador de relatórios para funcionários"""

    @staticmethod
    def gerar_relatorio_funcionarios(tenant, formato="pdf"):
        """Gera relatório geral de funcionários"""

        funcionarios = Funcionario.objects.filter(tenant=tenant, ativo=True)

        if formato == "pdf":
            return RelatorioFuncionarios._gerar_pdf_funcionarios(funcionarios, tenant)
        else:
            return RelatorioFuncionarios._gerar_excel_funcionarios(funcionarios)

    @staticmethod
    def _gerar_pdf_funcionarios(funcionarios, tenant):
        """Gera PDF com lista de funcionários"""

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []

        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=30,
            alignment=1,  # Center
        )

        # Título
        title = Paragraph(f"Relatório de Funcionários - {tenant.name}", title_style)
        story.append(title)
        story.append(Spacer(1, 12))

        # Data do relatório
        data_relatorio = Paragraph(f"Data: {date.today().strftime('%d/%m/%Y')}", styles["Normal"])
        story.append(data_relatorio)
        story.append(Spacer(1, 20))

        # Tabela de funcionários
        data = [["Nome", "CPF", "Cargo", "Admissão", "Salário"]]

        for funcionario in funcionarios:
            data.append(
                [
                    funcionario.nome_completo,
                    funcionario.cpf,
                    funcionario.cargo,
                    funcionario.data_admissao.strftime("%d/%m/%Y"),
                    f"R$ {funcionario.salario_base:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                ]
            )

        table = Table(data)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        story.append(table)

        # Resumo
        story.append(Spacer(1, 30))
        total_funcionarios = funcionarios.count()
        total_salarios = sum(f.salario_base for f in funcionarios)

        resumo = (
            f"""
        <b>Resumo:</b><br/>
        Total de Funcionários: {total_funcionarios}<br/>
        Total em Salários: R$ {total_salarios:,.2f}
        """.replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

        story.append(Paragraph(resumo, styles["Normal"]))

        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="relatorio_funcionarios_{date.today().strftime("%Y%m%d")}.pdf"'
        )
        response.write(buffer.getvalue())
        buffer.close()

        return response


class RelatorioPonto:
    """Gerador de relatórios de ponto"""

    @staticmethod
    def gerar_relatorio_ponto(funcionario, data_inicio, data_fim):
        """Gera relatório de ponto para um funcionário"""

        registros = CartaoPonto.objects.filter(
            funcionario=funcionario, data_hora_registro__date__range=[data_inicio, data_fim]
        ).order_by("data_hora_registro")

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []

        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("CustomTitle", parent=styles["Heading1"], fontSize=14, spaceAfter=20, alignment=1)

        # Título
        title = Paragraph(f"Relatório de Ponto - {funcionario.nome_completo}", title_style)
        story.append(title)

        # Período
        periodo = Paragraph(
            f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}", styles["Normal"]
        )
        story.append(periodo)
        story.append(Spacer(1, 20))

        # Agrupar registros por dia
        registros_por_dia = {}
        for registro in registros:
            data = registro.data_hora_registro.date()
            if data not in registros_por_dia:
                registros_por_dia[data] = []
            registros_por_dia[data].append(registro)

        # Tabela por dia
        for data, registros_dia in sorted(registros_por_dia.items()):
            # Cabeçalho do dia
            dia_header = Paragraph(f"<b>{data.strftime('%d/%m/%Y - %A')}</b>", styles["Heading3"])
            story.append(dia_header)

            # Tabela de registros do dia
            data_table = [["Horário", "Tipo", "IP", "Aprovado"]]

            for registro in registros_dia:
                data_table.append(
                    [
                        registro.data_hora_registro.strftime("%H:%M:%S"),
                        registro.get_tipo_registro_display(),
                        registro.ip_origem or "-",
                        "Sim" if registro.aprovado else "Não",
                    ]
                )

            table = Table(data_table)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )

            story.append(table)

            # Calcular horas do dia
            registros_dict = [
                {"data_hora_registro": r.data_hora_registro, "tipo_registro": r.tipo_registro} for r in registros_dia
            ]

            horas = CalculadoraBancoHoras.calcular_horas_trabalhadas(registros_dict)

            resumo_dia = f"Horas trabalhadas: {horas['total_horas']:.2f}h | Extras: {horas['horas_extras']:.2f}h"
            story.append(Paragraph(resumo_dia, styles["Normal"]))
            story.append(Spacer(1, 15))

        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="ponto_{funcionario.nome_completo.replace(" ", "_")}_{data_inicio.strftime("%Y%m%d")}_{data_fim.strftime("%Y%m%d")}.pdf"'
        )
        response.write(buffer.getvalue())
        buffer.close()

        return response


class RelatorioMaoObra:
    """Gerador de relatórios de mão de obra"""

    @staticmethod
    def gerar_relatorio_custos(tenant, incluir_inativos=False):
        """Gera relatório de custos de mão de obra"""

        funcionarios = Funcionario.objects.filter(tenant=tenant)
        if not incluir_inativos:
            funcionarios = funcionarios.filter(ativo=True)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []

        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("CustomTitle", parent=styles["Heading1"], fontSize=16, spaceAfter=30, alignment=1)

        # Título
        title = Paragraph(f"Relatório de Custos de Mão de Obra - {tenant.name}", title_style)
        story.append(title)
        story.append(Spacer(1, 12))

        # Data do relatório
        data_relatorio = Paragraph(f"Data: {date.today().strftime('%d/%m/%Y')}", styles["Normal"])
        story.append(data_relatorio)
        story.append(Spacer(1, 20))

        # Tabela de custos
        data = [["Funcionário", "Salário Base", "Custo Total/Mês", "Custo/Hora"]]

        custo_total_empresa = Decimal("0.00")

        for funcionario in funcionarios:
            custos = CalculadoraMaoObra.calcular_custo_total(funcionario)
            custo_total_empresa += custos["custo_total_mensal"]

            data.append(
                [
                    funcionario.nome_completo,
                    f"R$ {custos['salario_base']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    f"R$ {custos['custo_total_mensal']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    f"R$ {custos['custo_hora']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                ]
            )

        table = Table(data)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        story.append(table)

        # Resumo
        story.append(Spacer(1, 30))
        total_funcionarios = funcionarios.count()

        resumo = (
            f"""
        <b>Resumo:</b><br/>
        Total de Funcionários: {total_funcionarios}<br/>
        Custo Total Mensal: R$ {custo_total_empresa:,.2f}<br/>
        Custo Total Anual: R$ {custo_total_empresa * 12:,.2f}
        """.replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

        story.append(Paragraph(resumo, styles["Normal"]))

        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="relatorio_custos_mao_obra_{date.today().strftime("%Y%m%d")}.pdf"'
        )
        response.write(buffer.getvalue())
        buffer.close()

        return response


class RelatorioFerias:
    """Gerador de relatórios de férias"""

    @staticmethod
    def gerar_relatorio_ferias_vencidas(tenant):
        """Gera relatório de férias vencidas"""

        from dateutil.relativedelta import relativedelta

        # Funcionários com férias vencidas (mais de 12 meses do período aquisitivo)
        data_limite = date.today() - relativedelta(months=12)

        funcionarios_ferias_vencidas = []

        for funcionario in Funcionario.objects.filter(tenant=tenant, ativo=True):
            # Verifica se tem férias pendentes
            ultima_ferias = (
                Ferias.objects.filter(funcionario=funcionario, status="CONCLUIDA")
                .order_by("-periodo_aquisitivo_fim")
                .first()
            )

            if ultima_ferias:
                proximo_periodo = ultima_ferias.periodo_aquisitivo_fim + relativedelta(days=1)
            else:
                proximo_periodo = funcionario.data_admissao

            if proximo_periodo <= data_limite:
                funcionarios_ferias_vencidas.append({"funcionario": funcionario, "periodo_vencido": proximo_periodo})

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []

        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("CustomTitle", parent=styles["Heading1"], fontSize=16, spaceAfter=30, alignment=1)

        # Título
        title = Paragraph(f"Relatório de Férias Vencidas - {tenant.name}", title_style)
        story.append(title)
        story.append(Spacer(1, 12))

        # Data do relatório
        data_relatorio = Paragraph(f"Data: {date.today().strftime('%d/%m/%Y')}", styles["Normal"])
        story.append(data_relatorio)
        story.append(Spacer(1, 20))

        if funcionarios_ferias_vencidas:
            # Tabela de férias vencidas
            data = [["Funcionário", "Período Vencido", "Dias em Atraso"]]

            for item in funcionarios_ferias_vencidas:
                funcionario = item["funcionario"]
                periodo_vencido = item["periodo_vencido"]
                dias_atraso = (date.today() - periodo_vencido).days

                data.append([funcionario.nome_completo, periodo_vencido.strftime("%d/%m/%Y"), f"{dias_atraso} dias"])

            table = Table(data)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.red),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.lightpink),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )

            story.append(table)

            # Alerta
            story.append(Spacer(1, 20))
            alerta = Paragraph(
                "<b>ATENÇÃO:</b> Funcionários com férias vencidas podem gerar passivos trabalhistas!", styles["Normal"]
            )
            story.append(alerta)
        else:
            # Nenhuma férias vencida
            mensagem = Paragraph("✓ Nenhum funcionário com férias vencidas encontrado.", styles["Normal"])
            story.append(mensagem)

        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="relatorio_ferias_vencidas_{date.today().strftime("%Y%m%d")}.pdf"'
        )
        response.write(buffer.getvalue())
        buffer.close()

        return response
