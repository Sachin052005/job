from django.urls import reverse

from adminpanel.forms import AdminCompanyForm
from adminpanel.mixins import (
    AdminCreateView,
    AdminDeleteView,
    AdminDetailView,
    AdminListView,
    AdminUpdateView,
    FilterSpec,
    FixedParentMixin,
)
from companies.forms import CompanyOfficeForm, CompanyProductServiceForm, CompanySalaryForm
from companies.models import Company, CompanyFollow, CompanyOffice, CompanyProductService, CompanySalary
from core.constants import COMPANY_TYPE_CHOICES, VERIFICATION_STATUS_CHOICES


class BackToCompanyMixin:
    def get_success_url(self):
        return reverse("adminpanel:company_detail", kwargs={"pk": self.object.company_id})


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


class CompanyListView(AdminListView):
    model = Company
    page_title = "Companies"
    search_fields = ["name", "industry", "location", "owner__username"]
    columns = [
        ("Name", "name"),
        ("Owner", "owner.username"),
        ("Industry", "industry"),
        ("Location", "location"),
        ("Verification", "get_verification_status_display"),
        ("Active Jobs", "active_job_count"),
        ("Created", "created_at"),
    ]
    filter_specs = [
        FilterSpec("industry", "Company Type", COMPANY_TYPE_CHOICES, lookup="company_type"),
        FilterSpec("verification_status", "Verification", VERIFICATION_STATUS_CHOICES),
    ]
    add_url_name = "adminpanel:company_add"
    row_view_url_name = "adminpanel:company_detail"
    row_edit_url_name = "adminpanel:company_edit"
    row_delete_url_name = "adminpanel:company_delete"
    ordering = ["name"]
    select_related_fields = ["owner"]


class CompanyDetailView(AdminDetailView):
    model = Company
    template_name = "adminpanel/companies/detail.html"
    page_title = "Company"
    edit_url_name = "adminpanel:company_edit"
    delete_url_name = "adminpanel:company_delete"
    list_url_name = "adminpanel:company_list"
    detail_fields = [
        ("Name", "name"),
        ("Owner", "owner.username"),
        ("Industry", "industry"),
        ("Company type", "get_company_type_display"),
        ("Website", "website"),
        ("Location", "location"),
        ("Founded", "founded_year"),
        ("Size", "size"),
        ("Official email", "official_email"),
        ("Official phone", "official_phone"),
        ("Verification status", "get_verification_status_display"),
        ("Created", "created_at"),
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        company = self.object
        ctx.update(
            {
                "offices": company.offices.all(),
                "salaries": company.salaries.all(),
                "products_services": company.products_services.all(),
                "reviews": company.reviews.select_related("applicant").all()[:10],
                "review_average": company.review_average(),
                "follower_count": company.follower_count(),
                "jobs": company.jobs.all()[:10],
            }
        )
        return ctx


class CompanyCreateView(AdminCreateView):
    model = Company
    form_class = AdminCompanyForm
    page_title = "Add Company"
    list_url_name = "adminpanel:company_list"
    detail_url_name = "adminpanel:company_detail"


class CompanyUpdateView(AdminUpdateView):
    model = Company
    form_class = AdminCompanyForm
    page_title = "Edit Company"
    list_url_name = "adminpanel:company_list"
    detail_url_name = "adminpanel:company_detail"


class CompanyDeleteView(AdminDeleteView):
    model = Company
    page_title = "Delete Company"
    list_url_name = "adminpanel:company_list"


# ---------------------------------------------------------------------------
# Offices
# ---------------------------------------------------------------------------


class CompanyOfficeListView(AdminListView):
    model = CompanyOffice
    page_title = "Company Offices"
    search_fields = ["company__name", "city", "state"]
    columns = [("Company", "company.name"), ("Name", "name"), ("City", "city"), ("HQ", "is_headquarters")]
    row_edit_url_name = "adminpanel:office_edit"
    row_delete_url_name = "adminpanel:office_delete"
    select_related_fields = ["company"]


class CompanyOfficeCreateView(FixedParentMixin, BackToCompanyMixin, AdminCreateView):
    model = CompanyOffice
    form_class = CompanyOfficeForm
    parent_model = Company
    parent_url_kwarg = "company_pk"
    parent_field_name = "company"
    page_title = "Add Office"
    list_url_name = "adminpanel:office_list"


class CompanyOfficeUpdateView(BackToCompanyMixin, AdminUpdateView):
    model = CompanyOffice
    form_class = CompanyOfficeForm
    page_title = "Edit Office"
    list_url_name = "adminpanel:office_list"


class CompanyOfficeDeleteView(AdminDeleteView):
    model = CompanyOffice
    page_title = "Delete Office"
    list_url_name = "adminpanel:office_list"


# ---------------------------------------------------------------------------
# Salaries
# ---------------------------------------------------------------------------


class CompanySalaryListView(AdminListView):
    model = CompanySalary
    page_title = "Company Salaries"
    search_fields = ["company__name", "role"]
    columns = [("Company", "company.name"), ("Role", "role"), ("Range", "salary_range")]
    row_edit_url_name = "adminpanel:salary_edit"
    row_delete_url_name = "adminpanel:salary_delete"
    select_related_fields = ["company"]


class CompanySalaryCreateView(FixedParentMixin, BackToCompanyMixin, AdminCreateView):
    model = CompanySalary
    form_class = CompanySalaryForm
    parent_model = Company
    parent_url_kwarg = "company_pk"
    parent_field_name = "company"
    page_title = "Add Salary"
    list_url_name = "adminpanel:salary_list"


class CompanySalaryUpdateView(BackToCompanyMixin, AdminUpdateView):
    model = CompanySalary
    form_class = CompanySalaryForm
    page_title = "Edit Salary"
    list_url_name = "adminpanel:salary_list"


class CompanySalaryDeleteView(AdminDeleteView):
    model = CompanySalary
    page_title = "Delete Salary"
    list_url_name = "adminpanel:salary_list"


# ---------------------------------------------------------------------------
# Products & services
# ---------------------------------------------------------------------------


class CompanyProductServiceListView(AdminListView):
    model = CompanyProductService
    page_title = "Products & Services"
    search_fields = ["company__name", "name"]
    columns = [("Company", "company.name"), ("Name", "name"), ("Type", "get_item_type_display")]
    row_edit_url_name = "adminpanel:product_edit"
    row_delete_url_name = "adminpanel:product_delete"
    select_related_fields = ["company"]


class CompanyProductServiceCreateView(FixedParentMixin, BackToCompanyMixin, AdminCreateView):
    model = CompanyProductService
    form_class = CompanyProductServiceForm
    parent_model = Company
    parent_url_kwarg = "company_pk"
    parent_field_name = "company"
    page_title = "Add Product/Service"
    list_url_name = "adminpanel:product_list"


class CompanyProductServiceUpdateView(BackToCompanyMixin, AdminUpdateView):
    model = CompanyProductService
    form_class = CompanyProductServiceForm
    page_title = "Edit Product/Service"
    list_url_name = "adminpanel:product_list"


class CompanyProductServiceDeleteView(AdminDeleteView):
    model = CompanyProductService
    page_title = "Delete Product/Service"
    list_url_name = "adminpanel:product_list"


# ---------------------------------------------------------------------------
# Followers (read + delete only - a follow is a user action, not admin-authored)
# ---------------------------------------------------------------------------


class CompanyFollowListView(AdminListView):
    model = CompanyFollow
    page_title = "Company Followers"
    search_fields = ["company__name", "user__username"]
    columns = [("Company", "company.name"), ("Follower", "user.username"), ("Followed", "followed_at")]
    row_delete_url_name = "adminpanel:follower_delete"
    select_related_fields = ["company", "user"]


class CompanyFollowDeleteView(AdminDeleteView):
    model = CompanyFollow
    page_title = "Remove Follower"
    list_url_name = "adminpanel:follower_list"
