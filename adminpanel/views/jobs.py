from adminpanel.forms import AdminJobForm, CategoryForm
from adminpanel.mixins import (
    AdminCreateView,
    AdminDeleteView,
    AdminDetailView,
    AdminListView,
    AdminUpdateView,
    BulkAction,
    FilterSpec,
)
from core.constants import (
    APPLICATION_METHOD_CHOICES,
    EMPLOYMENT_TYPE_CHOICES,
    JOB_STATUS_CHOICES,
    JOB_STATUS_DRAFT,
    JOB_STATUS_PUBLISHED,
    WORK_MODE_CHOICES,
)
from jobs.models import Category, Job


class JobListView(AdminListView):
    model = Job
    page_title = "Jobs"
    search_fields = ["title", "company__name", "location", "skills", "employer__username"]
    columns = [
        ("Title", "title"),
        ("Company", "company.name"),
        ("Employer", "employer.username"),
        ("Category", "category.name"),
        ("Status", "get_status_display"),
        ("Employment Type", "get_employment_type_display"),
        ("Applications", "application_count"),
        ("Created", "created_at"),
    ]
    filter_specs = [
        FilterSpec("status", "Status", JOB_STATUS_CHOICES),
        FilterSpec("employment_type", "Employment Type", EMPLOYMENT_TYPE_CHOICES),
        FilterSpec("application_method", "Application Method", APPLICATION_METHOD_CHOICES),
        FilterSpec("work_mode", "Work Mode", WORK_MODE_CHOICES),
    ]
    add_url_name = "adminpanel:job_add"
    row_view_url_name = "adminpanel:job_detail"
    row_edit_url_name = "adminpanel:job_edit"
    row_delete_url_name = "adminpanel:job_delete"
    ordering = ["-created_at"]
    select_related_fields = ["company", "employer", "category"]
    bulk_actions = [
        BulkAction("publish", "Publish selected"),
        BulkAction("unpublish", "Unpublish (draft) selected"),
        BulkAction("delete", "Delete selected", "btn-outline-danger"),
    ]

    def bulk_publish(self, queryset):
        for job in queryset:
            job.status = JOB_STATUS_PUBLISHED
            job.save()

    def bulk_unpublish(self, queryset):
        queryset.update(status=JOB_STATUS_DRAFT)

    def bulk_delete(self, queryset):
        queryset.delete()


class JobDetailView(AdminDetailView):
    model = Job
    template_name = "adminpanel/jobs/detail.html"
    page_title = "Job"
    edit_url_name = "adminpanel:job_edit"
    delete_url_name = "adminpanel:job_delete"
    list_url_name = "adminpanel:job_list"
    detail_fields = [
        ("Title", "title"),
        ("Company", "company.name"),
        ("Employer", "employer.username"),
        ("Category", "category.name"),
        ("Location", "location"),
        ("Employment type", "get_employment_type_display"),
        ("Work mode", "get_work_mode_display"),
        ("Experience", "experience_min"),
        ("Education required", "get_education_required_display"),
        ("Salary min", "salary_min"),
        ("Salary max", "salary_max"),
        ("Application method", "get_application_method_display"),
        ("Status", "get_status_display"),
        ("Application deadline", "application_deadline"),
        ("Views", "views_count"),
        ("Created", "created_at"),
        ("Published", "published_at"),
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        job = self.object
        ctx.update(
            {
                "screening_questions": job.screening_questions.all(),
                "applications": job.applications.select_related("applicant")[:10],
                "application_count": job.application_count(),
            }
        )
        return ctx


class JobCreateView(AdminCreateView):
    model = Job
    form_class = AdminJobForm
    page_title = "Add Job"
    list_url_name = "adminpanel:job_list"
    detail_url_name = "adminpanel:job_detail"


class JobUpdateView(AdminUpdateView):
    model = Job
    form_class = AdminJobForm
    page_title = "Edit Job"
    list_url_name = "adminpanel:job_list"
    detail_url_name = "adminpanel:job_detail"


class JobDeleteView(AdminDeleteView):
    model = Job
    page_title = "Delete Job"
    list_url_name = "adminpanel:job_list"


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class CategoryListView(AdminListView):
    model = Category
    page_title = "Categories"
    search_fields = ["name"]
    columns = [("Name", "name"), ("Slug", "slug")]
    add_url_name = "adminpanel:category_add"
    row_edit_url_name = "adminpanel:category_edit"
    row_delete_url_name = "adminpanel:category_delete"
    ordering = ["name"]


class CategoryCreateView(AdminCreateView):
    model = Category
    form_class = CategoryForm
    page_title = "Add Category"
    list_url_name = "adminpanel:category_list"


class CategoryUpdateView(AdminUpdateView):
    model = Category
    form_class = CategoryForm
    page_title = "Edit Category"
    list_url_name = "adminpanel:category_list"


class CategoryDeleteView(AdminDeleteView):
    model = Category
    page_title = "Delete Category"
    list_url_name = "adminpanel:category_list"
