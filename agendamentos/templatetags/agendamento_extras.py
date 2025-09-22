from django import template

register = template.Library()


@register.filter(name="get_field")
def get_field(form, name):
    """Retorna o campo do form se existir, senão None."""
    try:
        return form.fields.get(name) and form[name]
    except Exception:
        return None


@register.filter(name="add_class")
def add_class(field, css):
    """Adiciona classes CSS ao widget mantendo as existentes."""
    if hasattr(field, "field"):
        existing = field.field.widget.attrs.get("class", "")
        classes = f"{existing} {css}".strip()
        field.field.widget.attrs["class"] = classes
    return field


@register.filter(name="has_group")
def has_group(user, group_name):
    """Verifica se o usuário pertence a um grupo específico."""
    if user.is_authenticated:
        return user.groups.filter(name=group_name).exists()
    return False
