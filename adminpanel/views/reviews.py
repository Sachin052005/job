from adminpanel.forms import CompanyReviewModerationForm
from adminpanel.mixins import AdminDeleteView, AdminDetailView, AdminListView, AdminUpdateView, BulkAction, FilterSpec
from companies.models import CompanyReview


class CompanyReviewListView(AdminListView):
    model = CompanyReview
    page_title = "Company Reviews"
    search_fields = ["company__name", "applicant__username", "content"]
    columns = [
        ("Company", "company.name"),
        ("Student", "reviewer_display_name"),
        ("Rating", "rating"),
        ("Active", "is_active"),
        ("Created", "created_at"),
    ]
    filter_specs = [
        FilterSpec("rating", "Rating", [(str(i), f"{i} star") for i in range(5, 0, -1)]),
        FilterSpec("is_active", "Status", [("1", "Active"), ("0", "Hidden")]),
    ]
    row_view_url_name = "adminpanel:review_detail"
    row_edit_url_name = "adminpanel:review_edit"
    row_delete_url_name = "adminpanel:review_delete"
    ordering = ["-created_at"]
    select_related_fields = ["company", "applicant"]
    bulk_actions = [
        BulkAction("activate", "Activate selected"),
        BulkAction("hide", "Hide selected"),
        BulkAction("delete", "Delete selected", "btn-outline-danger"),
    ]

    def bulk_activate(self, queryset):
        queryset.update(is_active=True)

    def bulk_hide(self, queryset):
        queryset.update(is_active=False)

    def bulk_delete(self, queryset):
        queryset.delete()


class CompanyReviewDetailView(AdminDetailView):
    model = CompanyReview
    page_title = "Company Review"
    edit_url_name = "adminpanel:review_edit"
    delete_url_name = "adminpanel:review_delete"
    list_url_name = "adminpanel:review_list"
    detail_fields = [
        ("Company", "company.name"),
        ("Student", "reviewer_display_name"),
        ("Rating", "rating"),
        ("Review", "content"),
        ("Image", "image"),
        ("Active", "is_active"),
        ("Created", "created_at"),
    ]


class CompanyReviewUpdateView(AdminUpdateView):
    """Moderation only (is_active) - see CompanyReviewModerationForm (spec section 21)."""

    model = CompanyReview
    form_class = CompanyReviewModerationForm
    page_title = "Moderate Review"
    list_url_name = "adminpanel:review_list"
    detail_url_name = "adminpanel:review_detail"
    success_message = "Review moderation updated."


class CompanyReviewDeleteView(AdminDeleteView):
    model = CompanyReview
    page_title = "Delete Review"
    list_url_name = "adminpanel:review_list"
