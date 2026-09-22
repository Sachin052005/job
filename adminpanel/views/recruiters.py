from accounts.models import RecruiterProfile
from adminpanel.forms import AdminRecruiterProfileForm
from adminpanel.mixins import AdminDeleteView, AdminDetailView, AdminListView, AdminUpdateView, BulkAction, FilterSpec
from core.constants import VERIFICATION_STATUS_CHOICES, VERIFICATION_UNVERIFIED, VERIFICATION_VERIFIED


class RecruiterProfileListView(AdminListView):
    model = RecruiterProfile
    page_title = "Recruiter Profiles"
    search_fields = ["user__username", "company__name", "designation"]
    columns = [
        ("User", "user.username"),
        ("Company", "company.name"),
        ("Designation", "designation"),
        ("Verification", "get_verification_status_display"),
        ("Created", "created_at"),
    ]
    filter_specs = [FilterSpec("verification_status", "Verification", VERIFICATION_STATUS_CHOICES)]
    row_view_url_name = "adminpanel:recruiter_detail"
    row_edit_url_name = "adminpanel:recruiter_edit"
    row_delete_url_name = "adminpanel:recruiter_delete"
    ordering = ["-created_at"]
    select_related_fields = ["user", "company"]
    bulk_actions = [
        BulkAction("verify", "Mark Verified"),
        BulkAction("unverify", "Mark Unverified"),
        BulkAction("delete", "Delete selected", "btn-outline-danger"),
    ]

    def bulk_verify(self, queryset):
        queryset.update(verification_status=VERIFICATION_VERIFIED)

    def bulk_unverify(self, queryset):
        queryset.update(verification_status=VERIFICATION_UNVERIFIED)

    def bulk_delete(self, queryset):
        queryset.delete()


class RecruiterProfileDetailView(AdminDetailView):
    model = RecruiterProfile
    page_title = "Recruiter Profile"
    edit_url_name = "adminpanel:recruiter_edit"
    delete_url_name = "adminpanel:recruiter_delete"
    list_url_name = "adminpanel:recruiter_list"
    detail_fields = [
        ("User", "user.username"),
        ("Company", "company.name"),
        ("Job title", "job_title"),
        ("Department", "department"),
        ("Designation", "designation"),
        ("Specialization", "get_specialization_display"),
        ("Official email", "official_company_email"),
        ("Employee ID", "employee_id"),
        ("Verification status", "get_verification_status_display"),
        ("Created", "created_at"),
    ]


class RecruiterProfileUpdateView(AdminUpdateView):
    model = RecruiterProfile
    form_class = AdminRecruiterProfileForm
    page_title = "Edit Recruiter Profile"
    list_url_name = "adminpanel:recruiter_list"
    detail_url_name = "adminpanel:recruiter_detail"


class RecruiterProfileDeleteView(AdminDeleteView):
    model = RecruiterProfile
    page_title = "Delete Recruiter Profile"
    list_url_name = "adminpanel:recruiter_list"
