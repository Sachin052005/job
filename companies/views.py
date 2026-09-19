from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from companies.forms import CompanyForm
from companies.models import Company
from core.constants import PAGE_SIZE
from core.permissions import EmployerRequiredMixin, OwnerRequiredMixin


class CompanyListView(ListView):
    model = Company
    template_name = "companies/company_list.html"
    context_object_name = "companies"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        queryset = Company.objects.all()
        keyword = self.request.GET.get("keyword", "").strip()
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        return queryset


class CompanyDetailView(DetailView):
    model = Company
    template_name = "companies/company_detail.html"
    context_object_name = "company"
    slug_url_kwarg = "slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        jobs = self.object.jobs.filter(status="published").select_related("category")
        paginator = Paginator(jobs, PAGE_SIZE)
        context["page_obj"] = paginator.get_page(self.request.GET.get("page"))
        return context


class CompanyCreateView(EmployerRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm
    template_name = "companies/company_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and hasattr(request.user, "company"):
            return redirect("companies:edit", slug=request.user.company.slug)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Company profile created.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("companies:detail", kwargs={"slug": self.object.slug})


class CompanyUpdateView(EmployerRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Company
    form_class = CompanyForm
    template_name = "companies/company_form.html"
    owner_field = "owner"
    slug_url_kwarg = "slug"

    def get_success_url(self):
        messages.success(self.request, "Company profile updated.")
        return reverse_lazy("companies:detail", kwargs={"slug": self.object.slug})
