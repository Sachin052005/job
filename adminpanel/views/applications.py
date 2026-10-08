from django.contrib import messages
from django.contrib.admin.models import CHANGE
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from adminpanel.mixins import (
    AdminDeleteView,
    AdminDetailView,
    AdminListView,
    AdminRequiredMixin,
    BulkAction,
    FilterSpec,
    log_admin_action,
)
from applications.forms import ApplicationStatusForm
from applications.models import Application
from core.constants import (
    APPLICATION_STATUS_CHOICES,
    APPLICATION_STATUS_HIRED,
    APPLICATION_STATUS_INTERVIEW,
    APPLICATION_STATUS_REJECTED,
    APPLICATION_STATUS_SHORTLISTED,
    APPLICATION_STATUS_UNDER_REVIEW,
    APPLIED_VIA_CHOICES,
)


class ApplicationListView(AdminListView):
    model = Application
    page_title = "Applications"
    search_fields = [
        "first_name", "last_name", "email", "applicant__username", "job__title", "job__company__name",
    ]
    columns = [
        ("Candidate", "full_name"),
        ("Job", "job.title"),
        ("Company", "job.company.name"),
        ("Status", "get_status_display"),
        ("Applied Via", "get_applied_via_display"),
        ("Match %", "match_percentage"),
        ("Applied", "applied_at"),
    ]
    filter_specs = [
        FilterSpec("status", "Status", APPLICATION_STATUS_CHOICES),
        FilterSpec("applied_via", "Applied Via", APPLIED_VIA_CHOICES),
    ]
    row_view_url_name = "adminpanel:application_detail"
    row_edit_url_name = "adminpanel:application_status"
    row_delete_url_name = "adminpanel:application_delete"
    ordering = ["-applied_at"]
    select_related_fields = ["job", "job__company", "applicant"]
    bulk_actions = [
        BulkAction("under_review", "Mark Under Review"),
        BulkAction("shortlisted", "Mark Shortlisted"),
        BulkAction("interview", "Mark Interview"),
        BulkAction("hired", "Mark Selected / Hired"),
        BulkAction("rejected", "Mark Rejected", "btn-outline-danger"),
    ]

    def _bulk_status(self, queryset, status):
        # Application.record_status_change() (spec section 45: reuse, don't
        # duplicate) - writes the ApplicationStatusHistory row for each item.
        for application in queryset:
            application.record_status_change(status, changed_by=self.request.user)

    def bulk_under_review(self, queryset):
        self._bulk_status(queryset, APPLICATION_STATUS_UNDER_REVIEW)

    def bulk_shortlisted(self, queryset):
        self._bulk_status(queryset, APPLICATION_STATUS_SHORTLISTED)

    def bulk_interview(self, queryset):
        self._bulk_status(queryset, APPLICATION_STATUS_INTERVIEW)

    def bulk_hired(self, queryset):
        self._bulk_status(queryset, APPLICATION_STATUS_HIRED)

    def bulk_rejected(self, queryset):
        self._bulk_status(queryset, APPLICATION_STATUS_REJECTED)


class ApplicationDetailView(AdminDetailView):
    model = Application
    template_name = "adminpanel/applications/detail.html"
    page_title = "Application"
    delete_url_name = "adminpanel:application_delete"
    list_url_name = "adminpanel:application_list"
    detail_fields = [
        ("Candidate", "full_name"),
        ("Applicant account", "applicant.username"),
        ("Job", "job.title"),
        ("Company", "job.company.name"),
        ("Email", "email"),
        ("Phone", "phone"),
        ("Location", "location"),
        ("Current company", "current_company"),
        ("Current title", "current_title"),
        ("Experience (years)", "experience_years"),
        ("Education", "education_summary"),
        ("Skills", "skills"),
        ("Resume", "resume"),
        ("LinkedIn", "linkedin_url"),
        ("GitHub", "github_url"),
        ("Portfolio", "portfolio_url"),
        ("Status", "get_status_display"),
        ("Applied via", "get_applied_via_display"),
        ("Match %", "match_percentage"),
        ("Applied at", "applied_at"),
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        application = self.object
        ctx.update(
            {
                "status_history": application.status_history.select_related("changed_by"),
                "match_snapshot": application.match_snapshot,
                "status_update_url": reverse("adminpanel:application_status", kwargs={"pk": application.pk}),
            }
        )
        return ctx


class ApplicationStatusUpdateView(AdminRequiredMixin, View):
    """Dedicated status-change view (not a generic AdminUpdateView) so a
    status edit always goes through Application.record_status_change() -
    the same path the rest of the app uses - instead of a raw form.save()
    that would silently skip writing ApplicationStatusHistory (spec sections
    20/45)."""

    template_name = "adminpanel/generic_form.html"

    def get(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        return self._render(request, application, ApplicationStatusForm(instance=application))

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        form = ApplicationStatusForm(request.POST, instance=application)
        if form.is_valid():
            new_status = form.cleaned_data["status"]
            # ModelForm validation (_post_clean) writes the new value onto
            # `application.status` in memory even though we never call
            # form.save() - undo that before calling record_status_change(),
            # whose "no-op if unchanged" check needs the real DB value to
            # compare against, or it silently skips the update + history row.
            application.refresh_from_db()
            application.record_status_change(new_status, changed_by=request.user)
            log_admin_action(request, application, CHANGE, message=f"Status changed to '{new_status}'.")
            messages.success(request, "Application status updated.")
            return redirect("adminpanel:application_detail", pk=application.pk)
        return self._render(request, application, form)

    def _render(self, request, application, form):
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "page_title": f"Update status — {application.full_name()}",
                "back_url": reverse("adminpanel:application_detail", kwargs={"pk": application.pk}),
            },
        )


class ApplicationDeleteView(AdminDeleteView):
    model = Application
    page_title = "Delete Application"
    list_url_name = "adminpanel:application_list"
