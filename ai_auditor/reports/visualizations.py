import base64
import io

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px


class ReportVisualizations:
    def plot_issue_severity(self, issues_data: dict) -> str:
        """Gera um gráfico de pizza da severidade dos problemas"""
        labels = issues_data.keys()
        sizes = issues_data.values()

        fig1, ax1 = plt.subplots()
        ax1.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
        ax1.axis("equal")  # Equal aspect ratio ensures that pie is drawn as a circle.

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        plt.close(fig1)
        image_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{image_base64}"

    def plot_issues_over_time(self, issues_over_time_data: dict) -> str:
        """Gera um gráfico de linha da evolução dos problemas ao longo do tempo"""
        df = pd.DataFrame(issues_over_time_data)
        fig = px.line(df, x="date", y="count", title="Problemas ao Longo do Tempo")
        return fig.to_html(full_html=False)
