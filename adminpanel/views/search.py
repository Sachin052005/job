from django.contrib.auth import get_user_model
from django.db.models import Q
from django.views.generic import TemplateView

from adminpanel.mixins import AdminRequiredMixin
from applications.models import Application
from companies.models import Company, CompanyReview
from jobs.models import Job

User = get_user_model()


class GlobalSearchView(AdminRequiredMixin, TemplateView):
    """Topbar search (spec section 42) - a real, bounded, database query
    across Users/Companies/Jobs/Applications/Reviews, not a full table scan
    (each queryset is icontains-filtered and sliced)."""

    template_name = "adminpanel/search_results.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        ctx["query"] = query
        if query:
            ctx["users"] = User.objects.filter(
                Q(username__icontains=query) | Q(email__icontains=query) | Q(first_name__icontains=query)
            ).select_related("profile")[:10]
            ctx["companies"] = Company.objects.filter(
                Q(name__icontains=query) | Q(industry__icontains=query) | Q(location__icontains=query)
            )[:10]
            ctx["jobs"] = Job.objects.filter(
                Q(title__icontains=query) | Q(location__icontains=query) | Q(skills__icontains=query)
            ).select_related("company")[:10]
            ctx["applications"] = Application.objects.filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query)
            ).select_related("job")[:10]
            ctx["reviews"] = CompanyReview.objects.filter(
                Q(content__icontains=query) | Q(company__name__icontains=query)
            ).select_related("company")[:10]
        else:
            ctx["users"] = ctx["companies"] = ctx["jobs"] = ctx["applications"] = ctx["reviews"] = []
        return ctx
