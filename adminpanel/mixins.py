"""Shared building blocks for the manual NammaCareer admin panel.

Every list/detail/create/update/delete view in adminpanel/views/ is a thin
subclass of the generic views below, configured with a handful of class
attributes (columns, search_fields, filter_specs, ...). This keeps ~30
managed models from requiring ~30 hand-written CRUD implementations while
still using real Django ModelForms/QuerySets against the live database
(spec sections 40-41: one reusable base, not a mockup).

Admin identity is `request.user.is_staff` (see core/permissions.py for the
matching `admin_required` decorator) - superusers automatically satisfy
`is_staff` in Django, so no separate superuser check is needed.
"""
from dataclasses import dataclass

from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Gate every manual-admin view on is_staff or is_superuser.

    No `login_url` override - falls back to settings.LOGIN_URL
    ("accounts:login"), the single login page for the whole site. There is
    no separate admin login route/page.
    """

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(self.request.get_full_path())
        raise PermissionDenied("Only staff accounts can access the NammaCareer admin panel.")


def log_admin_action(request, obj, action_flag, message=""):
    """Record an admin-panel mutation using Django's own LogEntry (spec
    section 36 explicitly prefers reusing it over a duplicate audit model)."""
    content_type = ContentType.objects.get_for_model(obj.__class__)
    LogEntry.objects.log_action(
        user_id=request.user.pk,
        content_type_id=content_type.pk,
        object_id=obj.pk,
        object_repr=str(obj)[:200],
        action_flag=action_flag,
        change_message=message,
    )


@dataclass
class FilterSpec:
    param: str
    label: str
    choices: list
    lookup: str = ""

    def __post_init__(self):
        if not self.lookup:
            self.lookup = self.param


@dataclass
class BulkAction:
    key: str
    label: str
    css_class: str = "btn-outline-secondary"


class AdminListView(AdminRequiredMixin, ListView):
    """Generic searchable/filterable/paginated list page (spec sections 11-13)."""

    template_name = "adminpanel/generic_list.html"
    paginate_by = 25
    search_fields = ()
    filter_specs = ()
    columns = ()  # sequence of (label, dotted_path)
    page_title = ""
    add_url_name = None
    row_view_url_name = None
    row_edit_url_name = None
    row_delete_url_name = None
    ordering = None
    select_related_fields = ()
    prefetch_related_fields = ()
    bulk_actions = ()  # sequence of BulkAction

    def get_queryset(self):
        qs = super().get_queryset()
        if self.select_related_fields:
            qs = qs.select_related(*self.select_related_fields)
        if self.prefetch_related_fields:
            qs = qs.prefetch_related(*self.prefetch_related_fields)

        self.search_query = self.request.GET.get("q", "").strip()
        if self.search_query and self.search_fields:
            condition = Q()
            for lookup in self.search_fields:
                condition |= Q(**{f"{lookup}__icontains": self.search_query})
            qs = qs.filter(condition).distinct()

        self.active_filters = {}
        for spec in self.filter_specs:
            value = self.request.GET.get(spec.param, "").strip()
            if value:
                qs = qs.filter(**{spec.lookup: value})
                self.active_filters[spec.param] = value

        if self.ordering:
            qs = qs.order_by(*self.ordering)
        return qs

    def post(self, request, *args, **kwargs):
        """Bulk actions (spec section 15) - always POST, always server-validated."""
        action = request.POST.get("bulk_action", "").strip()
        ids = [pk for pk in request.POST.getlist("selected") if pk]
        handler = getattr(self, f"bulk_{action}", None) if action else None
        if not ids:
            messages.warning(request, "No rows were selected.")
        elif not handler:
            messages.error(request, "Unknown bulk action.")
        else:
            queryset = self.model.objects.filter(pk__in=ids)
            count = queryset.count()
            handler(queryset)
            messages.success(request, f"Applied '{action}' to {count} item(s).")
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        preserved = self.request.GET.copy()
        preserved.pop("page", None)
        ctx.update(
            {
                "page_title": self.page_title,
                "columns": self.columns,
                "search_query": getattr(self, "search_query", ""),
                "search_enabled": bool(self.search_fields),
                "filter_specs": self.filter_specs,
                "active_filters": getattr(self, "active_filters", {}),
                "add_url": reverse(self.add_url_name) if self.add_url_name else None,
                "row_view_url_name": self.row_view_url_name,
                "row_edit_url_name": self.row_edit_url_name,
                "row_delete_url_name": self.row_delete_url_name,
                "bulk_actions": self.bulk_actions,
                "preserved_querystring": preserved.urlencode(),
            }
        )
        return ctx


class AdminDetailView(AdminRequiredMixin, DetailView):
    """Generic read-only detail page. Resources with related objects (Company,
    Job, Application, Profile, User) override get_context_data() to add
    `related_sections` instead of using this directly (spec section 33)."""

    template_name = "adminpanel/generic_detail.html"
    page_title = ""
    detail_fields = ()  # sequence of (label, dotted_path)
    edit_url_name = None
    delete_url_name = None
    list_url_name = None
    related_sections = ()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            {
                "page_title": self.page_title,
                "detail_fields": self.detail_fields,
                "edit_url_name": self.edit_url_name,
                "delete_url_name": self.delete_url_name,
                "list_url_name": self.list_url_name,
                "related_sections": self.related_sections,
            }
        )
        return ctx


class AdminFormViewMixin:
    template_name = "adminpanel/generic_form.html"
    page_title = ""
    list_url_name = None
    detail_url_name = None

    def get_back_url(self):
        obj = getattr(self, "object", None)
        if self.detail_url_name and obj is not None and obj.pk:
            return reverse(self.detail_url_name, kwargs={"pk": obj.pk})
        if self.list_url_name:
            return reverse(self.list_url_name)
        return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"page_title": self.page_title, "back_url": self.get_back_url()})
        return ctx

    def get_success_url(self):
        if self.detail_url_name:
            return reverse(self.detail_url_name, kwargs={"pk": self.object.pk})
        return reverse(self.list_url_name)


class AdminCreateView(AdminFormViewMixin, AdminRequiredMixin, CreateView):
    success_message = "Created successfully."

    def form_valid(self, form):
        response = super().form_valid(form)
        log_admin_action(self.request, self.object, ADDITION)
        messages.success(self.request, self.success_message)
        return response


class AdminUpdateView(AdminFormViewMixin, AdminRequiredMixin, UpdateView):
    success_message = "Saved successfully."

    def form_valid(self, form):
        response = super().form_valid(form)
        log_admin_action(self.request, self.object, CHANGE, message="Changed via admin panel.")
        messages.success(self.request, self.success_message)
        return response


class AdminDeleteView(AdminRequiredMixin, DeleteView):
    template_name = "adminpanel/generic_confirm_delete.html"
    page_title = ""
    list_url_name = None

    def get_success_url(self):
        return reverse(self.list_url_name)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"page_title": self.page_title, "list_url_name": self.list_url_name})
        return ctx

    def form_valid(self, form):
        # Django >=5.0's DeleteView is FormMixin-based: POST goes through
        # form_valid() (which calls self.object.delete() itself), not the
        # legacy delete() hook - overriding delete() here would silently
        # never run. See BaseDeleteView.form_valid() in django/views/generic/edit.py.
        object_repr = str(self.object)
        object_pk = self.object.pk
        content_type = ContentType.objects.get_for_model(self.object.__class__)
        response = super().form_valid(form)
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=content_type.pk,
            object_id=object_pk,
            object_repr=object_repr[:200],
            action_flag=DELETION,
        )
        messages.success(self.request, f"Deleted: {object_repr}")
        return response


class FixedParentMixin:
    """For "child" resources created from a parent's detail page (e.g. add an
    Education record from a Profile's detail page) - injects the parent FK
    from the URL instead of exposing it as an editable form field."""

    parent_model = None
    parent_url_kwarg = "profile_pk"
    parent_field_name = "profile"

    def get_parent_object(self):
        return self.parent_model.objects.get(pk=self.kwargs[self.parent_url_kwarg])

    def form_valid(self, form):
        setattr(form.instance, self.parent_field_name, self.get_parent_object())
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["parent_object"] = self.get_parent_object()
        return ctx
