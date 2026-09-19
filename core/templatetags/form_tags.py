from django import template

register = template.Library()


@register.filter(name="add_class")
def add_class(field, css_class):
    existing = field.field.widget.attrs.get("class", "")
    classes = f"{existing} {css_class}".strip()
    return field.as_widget(attrs={**field.field.widget.attrs, "class": classes})
