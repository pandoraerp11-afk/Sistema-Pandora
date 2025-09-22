import pandas as pd
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


class ReportExporter:
    def export_to_excel(self, queryset, filename="report.xlsx"):
        df = pd.DataFrame(list(queryset.values()))
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename={filename}"
        df.to_excel(response, index=False)
        return response

    def export_to_pdf(self, queryset, filename="report.pdf"):
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename={filename}"

        p = canvas.Canvas(filename, pagesize=letter)
        # Implementar lógica para desenhar o conteúdo do PDF
        p.drawString(100, 750, "Relatório de Auditoria de IA")
        p.showPage()
        p.save()
        return response

    def export_to_csv(self, queryset, filename="report.csv"):
        df = pd.DataFrame(list(queryset.values()))
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f"attachment; filename={filename}"
        df.to_csv(response, index=False)
        return response
