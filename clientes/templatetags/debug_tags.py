from django import template

register = template.Library()


@register.filter
def class_name(obj):
    """Retorna o nome da classe do objeto"""
    if obj is None:
        return "None"
    return obj.__class__.__name__


@register.filter
def model_name(obj):
    """Retorna o nome do model se for um ModelForm"""
    if hasattr(obj, "_meta") and hasattr(obj._meta, "model"):
        return obj._meta.model.__name__
    return "N/A"
