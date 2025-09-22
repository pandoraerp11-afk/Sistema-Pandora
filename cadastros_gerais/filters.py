# cadastros_gerais/filters.py
import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import UnidadeMedida


class UnidadeMedidaFilter(django_filters.FilterSet):
    # Um único campo de busca que procura em 'nome' E 'simbolo'
    termo = django_filters.CharFilter(
        method="filtro_geral",
        label=_("Buscar"),
        widget=django_filters.widgets.forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nome ou Símbolo..."}
        ),
    )

    class Meta:
        model = UnidadeMedida
        fields = ["termo"]

    def filtro_geral(self, queryset, name, value):
        if value:
            return queryset.filter(Q(nome__icontains=value) | Q(simbolo__icontains=value))
        return queryset
