from django import template

register = template.Library()


@register.filter
def resolve(obj, path):
    """Resolve a dotted attribute/method path (e.g. "job.company.name") for
    generic list/detail templates so column/field definitions can stay data,
    not per-template markup (spec sections 40-41)."""
    value = obj
    for part in path.split("."):
        if value is None or value == "":
            return ""
        value = getattr(value, part, "")
        if callable(value):
            try:
                value = value()
            except TypeError:
                return ""
    return value


@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return None
    return dictionary.get(key)


@register.simple_tag(takes_context=True)
def querystring_with(context, **kwargs):
    """Current GET querystring with the given keys overridden - used for
    pagination/sort links that must preserve active search+filters."""
    request = context["request"]
    query = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()
