from accounts.forms import JobAlertForm
from accounts.models import JobAlert
from adminpanel.mixins import AdminDeleteView, AdminDetailView, AdminListView, AdminUpdateView, BulkAction, FilterSpec


class JobAlertListView(AdminListView):
    model = JobAlert
    page_title = "Job Alerts"
    search_fields = ["user__username", "name", "keywords", "location"]
    columns = [
        ("User", "user.username"),
        ("Name", "name"),
        ("Frequency", "get_frequency_display"),
        ("Active", "is_active"),
        ("Created", "created_at"),
    ]
    filter_specs = [FilterSpec("is_active", "Status", [("1", "Active"), ("0", "Inactive")])]
    row_view_url_name = "adminpanel:jobalert_detail"
    row_edit_url_name = "adminpanel:jobalert_edit"
    row_delete_url_name = "adminpanel:jobalert_delete"
    ordering = ["-created_at"]
    select_related_fields = ["user", "domain"]
    bulk_actions = [
        BulkAction("activate", "Activate selected"),
        BulkAction("deactivate", "Deactivate selected"),
        BulkAction("delete", "Delete selected", "btn-outline-danger"),
    ]

    def bulk_activate(self, queryset):
        queryset.update(is_active=True)

    def bulk_deactivate(self, queryset):
        queryset.update(is_active=False)

    def bulk_delete(self, queryset):
        queryset.delete()


class JobAlertDetailView(AdminDetailView):
    model = JobAlert
    page_title = "Job Alert"
    edit_url_name = "adminpanel:jobalert_edit"
    delete_url_name = "adminpanel:jobalert_delete"
    list_url_name = "adminpanel:jobalert_list"
    detail_fields = [
        ("User", "user.username"),
        ("Name", "name"),
        ("Keywords", "keywords"),
        ("Domain", "domain.name"),
        ("Location", "location"),
        ("Max experience", "experience_max"),
        ("Min salary", "salary_min"),
        ("Employment type", "get_employment_type_display"),
        ("Work mode", "get_work_mode_display"),
        ("Frequency", "get_frequency_display"),
        ("Active", "is_active"),
        ("Created", "created_at"),
    ]


class JobAlertUpdateView(AdminUpdateView):
    model = JobAlert
    form_class = JobAlertForm
    page_title = "Edit Job Alert"
    list_url_name = "adminpanel:jobalert_list"
    detail_url_name = "adminpanel:jobalert_detail"


class JobAlertDeleteView(AdminDeleteView):
    model = JobAlert
    page_title = "Delete Job Alert"
    list_url_name = "adminpanel:jobalert_list"
