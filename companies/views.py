from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from companies.forms import (
    CompanyContentForm,
    CompanyForm,
    CompanyOfficeForm,
    CompanyProductServiceForm,
    CompanyReviewForm,
    CompanySalaryForm,
)
from companies.models import Company, CompanyFollow, CompanyOffice, CompanyProductService, CompanyReview, CompanySalary
from core.constants import NOTIFICATION_TYPE_COMPANY, PAGE_SIZE, ROLE_JOB_SEEKER
from core.permissions import EmployerRequiredMixin, OwnerRequiredMixin
from notifications.services import create_notification


def _hired_application_for_company(user, company):
    """Most recent Application where `user` reached the project's actual
    hired/selected state for a job at `company` (spec sections 9/10/32).

    Local import avoids a module-level companies<->applications import cycle
    (applications already imports jobs, which imports companies).
    """
    from applications.models import Application
    from core.constants import APPLICATION_STATUS_HIRED

    return (
        Application.objects.filter(applicant=user, job__company=company, status=APPLICATION_STATUS_HIRED)
        .order_by("-applied_at")
        .first()
    )


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
        industry = self.request.GET.get("industry", "").strip()
        if industry:
            queryset = queryset.filter(industry__icontains=industry)
        location = self.request.GET.get("location", "").strip()
        if location:
            queryset = queryset.filter(location__icontains=location)
        company_type = self.request.GET.get("company_type", "").strip()
        if company_type:
            queryset = queryset.filter(company_type=company_type)
        if self.request.GET.get("hiring") == "1":
            queryset = queryset.filter(jobs__status="published").distinct()
        if self.request.GET.get("hiring_freshers") == "1":
            queryset = queryset.filter(jobs__status="published", jobs__badges__icontains="freshers_can_apply").distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context["followed_company_ids"] = set(
                CompanyFollow.objects.filter(user=self.request.user).values_list("company_id", flat=True)
            )
        return context


class FollowedCompaniesListView(LoginRequiredMixin, ListView):
    model = CompanyFollow
    template_name = "companies/followed_companies.html"
    context_object_name = "follows"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        return CompanyFollow.objects.filter(user=self.request.user).select_related("company")


class CompanyDetailView(DetailView):
    model = Company
    template_name = "companies/company_detail.html"
    context_object_name = "company"
    slug_url_kwarg = "slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.object
        jobs = company.jobs.filter(status="published").select_related("category")
        paginator = Paginator(jobs, PAGE_SIZE)
        context["page_obj"] = paginator.get_page(self.request.GET.get("page"))
        context["tab"] = self.request.GET.get("tab", "overview")
        # Interview Questions / Benefits removed from the company profile (spec section 1).
        context["tabs"] = [
            ("overview", "Overview"),
            ("jobs", "Jobs"),
            ("reviews", "Reviews"),
            ("salaries", "Salaries"),
            ("culture", "Culture"),
            ("locations", "Locations"),
            ("products", "Products & Services"),
        ]
        context["follower_count"] = company.follower_count()
        context["offices"] = company.offices.all()
        context["salaries"] = company.salaries.all()
        context["products_services"] = company.products_services.all()

        reviews = company.active_reviews().order_by("-created_at")
        context["reviews"] = reviews
        context["review_count"] = company.review_count()
        review_average = company.review_average()
        context["review_average"] = review_average
        context["review_average_rounded"] = round(review_average) if review_average else 0
        context["review_breakdown"] = company.review_breakdown()

        context["is_following"] = False
        context["can_review"] = False
        context["has_reviewed"] = False
        if self.request.user.is_authenticated:
            context["is_following"] = CompanyFollow.objects.filter(
                user=self.request.user, company=company
            ).exists()
            profile = getattr(self.request.user, "profile", None)
            context["has_reviewed"] = CompanyReview.objects.filter(
                company=company, applicant=self.request.user
            ).exists()
            context["can_review"] = bool(
                profile
                and profile.role == ROLE_JOB_SEEKER
                and not context["has_reviewed"]
                and _hired_application_for_company(self.request.user, company)
            )
        return context


class FollowCompanyToggleView(LoginRequiredMixin, View):
    def post(self, request, slug):
        company = get_object_or_404(Company, slug=slug)
        follow, created = CompanyFollow.objects.get_or_create(user=request.user, company=company)
        if created:
            is_following = True
        else:
            follow.delete()
            is_following = False

        if request.htmx:
            return render(
                request, "companies/_follow_button.html", {"company": company, "is_following": is_following}
            )

        if is_following:
            messages.success(request, f"You are now following {company.name}.")
        else:
            messages.info(request, f"You unfollowed {company.name}.")
        next_url = request.POST.get("next") or "companies:detail"
        if next_url == "companies:detail":
            return redirect("companies:detail", slug=company.slug)
        return redirect(next_url)


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


class OwnedCompanyRecordMixin:
    """Shared CRUD scoping for a company's structured sub-records (Offices,
    Salaries, Products/Services) - mirrors accounts.views.OwnedProfileRecordMixin.

    Ensures an employer can only ever see/edit/delete records that belong to
    their own Company (no IDOR via pk-in-URL - another company's record 404s),
    and that the employer has a Company at all before reaching these pages
    (spec section 28: server-side ownership, not just hidden buttons).
    """

    success_url = reverse_lazy("companies:manage")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not hasattr(request.user, "company"):
            messages.warning(request, "Create your company profile before managing this section.")
            return redirect("companies:create")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if hasattr(form, "instance"):
            form.instance.company = self.request.user.company
        return form


class CompanyManageView(EmployerRequiredMixin, View):
    """Company Profile Management hub (spec section 27): Overview/Culture text
    is edited inline here; Salaries/Locations/Products & Services are managed
    as related records via the Add/Edit/Delete views below."""

    template_name = "companies/company_manage.html"

    def _require_company(self, request):
        # Role check (EmployerRequiredMixin) already ran via dispatch() before
        # get()/post() are called - this only handles "employer with no
        # Company yet", mirroring JobCreateView's _require_company.
        if not hasattr(request.user, "company"):
            messages.warning(request, "Create your company profile first.")
            return redirect("companies:create")
        return None

    def get(self, request, *args, **kwargs):
        redirect_response = self._require_company(request)
        if redirect_response:
            return redirect_response
        self.company = request.user.company
        return render(request, self.template_name, self._context(CompanyContentForm(instance=self.company)))

    def post(self, request, *args, **kwargs):
        redirect_response = self._require_company(request)
        if redirect_response:
            return redirect_response
        self.company = request.user.company
        form = CompanyContentForm(request.POST, instance=self.company)
        if form.is_valid():
            form.save()
            messages.success(request, "Company details updated.")
            return redirect("companies:manage")
        messages.error(request, "Please fix the errors below.")
        return render(request, self.template_name, self._context(form))

    def _context(self, content_form):
        return {
            "company": self.company,
            "content_form": content_form,
            "offices": self.company.offices.all(),
            "salaries": self.company.salaries.all(),
            "products_services": self.company.products_services.all(),
            "reviews": self.company.reviews.select_related("applicant").order_by("-created_at"),
        }


class CompanyOfficeCreateView(EmployerRequiredMixin, OwnedCompanyRecordMixin, CreateView):
    model = CompanyOffice
    form_class = CompanyOfficeForm
    template_name = "companies/record_form.html"
    extra_context = {"title": "Add Branch Location"}


class CompanyOfficeUpdateView(EmployerRequiredMixin, OwnedCompanyRecordMixin, UpdateView):
    model = CompanyOffice
    form_class = CompanyOfficeForm
    template_name = "companies/record_form.html"
    extra_context = {"title": "Edit Branch Location"}


class CompanyOfficeDeleteView(EmployerRequiredMixin, OwnedCompanyRecordMixin, DeleteView):
    model = CompanyOffice
    template_name = "companies/record_confirm_delete.html"
    extra_context = {"title": "branch location"}


class CompanySalaryCreateView(EmployerRequiredMixin, OwnedCompanyRecordMixin, CreateView):
    model = CompanySalary
    form_class = CompanySalaryForm
    template_name = "companies/record_form.html"
    extra_context = {"title": "Add Salary Information"}


class CompanySalaryUpdateView(EmployerRequiredMixin, OwnedCompanyRecordMixin, UpdateView):
    model = CompanySalary
    form_class = CompanySalaryForm
    template_name = "companies/record_form.html"
    extra_context = {"title": "Edit Salary Information"}


class CompanySalaryDeleteView(EmployerRequiredMixin, OwnedCompanyRecordMixin, DeleteView):
    model = CompanySalary
    template_name = "companies/record_confirm_delete.html"
    extra_context = {"title": "salary entry"}


class CompanyProductServiceCreateView(EmployerRequiredMixin, OwnedCompanyRecordMixin, CreateView):
    model = CompanyProductService
    form_class = CompanyProductServiceForm
    template_name = "companies/record_form.html"
    extra_context = {"title": "Add Product / Service"}


class CompanyProductServiceUpdateView(EmployerRequiredMixin, OwnedCompanyRecordMixin, UpdateView):
    model = CompanyProductService
    form_class = CompanyProductServiceForm
    template_name = "companies/record_form.html"
    extra_context = {"title": "Edit Product / Service"}


class CompanyProductServiceDeleteView(EmployerRequiredMixin, OwnedCompanyRecordMixin, DeleteView):
    model = CompanyProductService
    template_name = "companies/record_confirm_delete.html"
    extra_context = {"title": "product/service entry"}


class CompanyReviewToggleActiveView(EmployerRequiredMixin, View):
    """HR moderation (spec sections 20/21): hide/show a review without ever
    touching the student's rating or content."""

    def post(self, request, pk):
        review = get_object_or_404(CompanyReview.objects.select_related("company"), pk=pk)
        if not hasattr(request.user, "company") or review.company_id != request.user.company.pk:
            raise PermissionDenied("You do not own this company.")
        review.is_active = not review.is_active
        review.save(update_fields=["is_active"])
        messages.success(request, "Review visibility updated.")
        return redirect("companies:manage")


class CompanyReviewCreateView(LoginRequiredMixin, CreateView):
    """Verified Student Review (spec sections 9-15/23): eligibility - authenticated,
    job seeker, has a Hired application at this company, hasn't already reviewed
    it - is fully re-verified server-side on both GET and POST via dispatch()."""

    model = CompanyReview
    form_class = CompanyReviewForm
    template_name = "companies/company_review_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, slug=kwargs["slug"])
        if request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if not profile or profile.role != ROLE_JOB_SEEKER:
                raise PermissionDenied("Only job seekers can review a company.")
            if CompanyReview.objects.filter(company=self.company, applicant=request.user).exists():
                messages.info(request, "You have already reviewed this company.")
                return redirect(f"{reverse('companies:detail', kwargs={'slug': self.company.slug})}?tab=reviews")
            self.hired_application = _hired_application_for_company(request.user, self.company)
            if not self.hired_application:
                messages.error(
                    request, "You can review a company only after being hired for a role there."
                )
                return redirect("companies:detail", slug=self.company.slug)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["company"] = self.company
        return context

    def form_valid(self, form):
        form.instance.company = self.company
        form.instance.applicant = self.request.user
        form.instance.application = self.hired_application
        messages.success(self.request, "Thanks! Your review has been posted.")
        return super().form_valid(form)

    def get_success_url(self):
        return f"{reverse('companies:detail', kwargs={'slug': self.company.slug})}?tab=reviews"
