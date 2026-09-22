from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from applications.models import Application
from companies.models import Company
from core.constants import JOB_STATUS_CHOICES, JOB_STATUS_PUBLISHED, PAGE_SIZE
from core.permissions import EmployerRequiredMixin, OwnerRequiredMixin
from jobs.forms import JobForm, JobSearchForm
from jobs.models import Category, Job
from jobs.services import notify_job_published
from saved_jobs.models import SavedJob
from services.search_service import filter_jobs


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        published = Job.objects.filter(status=JOB_STATUS_PUBLISHED).select_related("company", "category")
        context["featured_jobs"] = published[:6]
        context["categories"] = Category.objects.all()[:8]
        context["total_jobs"] = published.count()
        context["total_companies"] = Company.objects.count()
        context["search_form"] = JobSearchForm()

        job_sections = []
        if self.request.user.is_authenticated and getattr(self.request.user, "profile", None):
            profile = self.request.user.profile
            skills = profile.effective_skills_list()
            if skills:
                from django.db.models import Q

                query = Q()
                for skill in skills[:8]:
                    query |= Q(skills__icontains=skill)
                recommended = published.filter(query).exclude(applications__applicant=self.request.user)[:10]
                if recommended:
                    job_sections.append({"title": "Jobs based on your profile", "jobs": recommended})

        categories_with_jobs = Category.objects.filter(jobs__status=JOB_STATUS_PUBLISHED).distinct()[:6]
        for category in categories_with_jobs:
            jobs = published.filter(category=category)[:10]
            if jobs:
                job_sections.append({"title": f"Jobs in {category.name}", "jobs": jobs})

        context["job_sections"] = job_sections
        return context


class JobListView(ListView):
    model = Job
    template_name = "jobs/job_list.html"
    context_object_name = "jobs"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        self.form = JobSearchForm(self.request.GET or None)
        queryset = Job.objects.all()
        if self.form.is_valid():
            params = {
                "keyword": self.form.cleaned_data.get("keyword"),
                "location": self.form.cleaned_data.get("location"),
                "category": self.form.cleaned_data.get("category").slug if self.form.cleaned_data.get("category") else "",
                "employment_type": self.form.cleaned_data.get("employment_type"),
                "experience": self.form.cleaned_data.get("experience"),
                "salary_min": self.form.cleaned_data.get("salary_min"),
                "freshers_only": self.form.cleaned_data.get("freshers_only"),
                "remote_only": self.form.cleaned_data.get("remote_only"),
                "urgent_only": self.form.cleaned_data.get("urgent_only"),
                "walkin_only": self.request.GET.get("walkin_only"),
                "work_mode": self.request.GET.get("work_mode"),
            }
            queryset = filter_jobs(queryset, params)
        else:
            queryset = queryset.filter(status=JOB_STATUS_PUBLISHED).select_related("company", "category")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = self.form
        context["querystring"] = self._querystring_without_page()
        if self.request.user.is_authenticated:
            context["saved_job_ids"] = set(
                SavedJob.objects.filter(user=self.request.user).values_list("job_id", flat=True)
            )
        return context

    def _querystring_without_page(self):
        query = self.request.GET.copy()
        query.pop("page", None)
        return query.urlencode()


class JobDetailView(DetailView):
    model = Job
    template_name = "jobs/job_detail.html"
    context_object_name = "job"

    def get_queryset(self):
        return Job.objects.select_related("company", "category", "employer")

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        job = self.object
        if not (request.user.is_authenticated and job.employer_id == request.user.id):
            Job.objects.filter(pk=job.pk).update(views_count=job.views_count + 1)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object
        context["is_owner"] = self.request.user.is_authenticated and job.employer_id == self.request.user.id
        if self.request.user.is_authenticated:
            context["has_applied"] = Application.objects.filter(job=job, applicant=self.request.user).exists()
            context["is_saved"] = SavedJob.objects.filter(job=job, user=self.request.user).exists()
            profile = getattr(self.request.user, "profile", None)
            context["easy_apply_ready"] = bool(profile and profile.is_easy_apply_ready())
            context["missing_easy_apply_fields"] = profile.missing_easy_apply_fields() if profile else []
        context["similar_jobs"] = (
            Job.objects.filter(status=JOB_STATUS_PUBLISHED, category=job.category)
            .exclude(pk=job.pk)
            .select_related("company")[:4]
        )
        return context


class JobCreateView(EmployerRequiredMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = "jobs/job_form.html"

    def _require_company(self, request):
        if not hasattr(request.user, "company"):
            messages.warning(request, "Create your company profile before posting a job.")
            return redirect("companies:create")
        return None

    def get(self, request, *args, **kwargs):
        redirect_response = self._require_company(request)
        if redirect_response:
            return redirect_response
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        redirect_response = self._require_company(request)
        if redirect_response:
            return redirect_response
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.employer = self.request.user
        form.instance.company = self.request.user.company
        response = super().form_valid(form)
        if self.object.status == JOB_STATUS_PUBLISHED:
            notify_job_published(self.object)
        messages.success(self.request, "Job posted successfully.")
        return response


class JobUpdateView(EmployerRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Job
    form_class = JobForm
    template_name = "jobs/job_form.html"
    owner_field = "employer"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        self._was_published = form.instance.status == JOB_STATUS_PUBLISHED
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.object.status == JOB_STATUS_PUBLISHED and not getattr(self, "_was_published", False):
            notify_job_published(self.object)
        return response

    def get_success_url(self):
        messages.success(self.request, "Job updated successfully.")
        return reverse_lazy("jobs:detail", kwargs={"pk": self.object.pk})


class JobDeleteView(EmployerRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Job
    template_name = "jobs/job_confirm_delete.html"
    success_url = reverse_lazy("dashboard:home")
    owner_field = "employer"

    def form_valid(self, form):
        messages.success(self.request, "Job deleted.")
        return super().form_valid(form)


class JobToggleStatusView(EmployerRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Job
    fields = []
    owner_field = "employer"

    def post(self, request, *args, **kwargs):
        job = self.get_object()
        status_map = dict(JOB_STATUS_CHOICES)
        new_status = request.POST.get("status")
        if new_status not in status_map:
            return HttpResponseForbidden("Invalid status.")
        was_published = job.status == JOB_STATUS_PUBLISHED
        job.status = new_status
        job.save(update_fields=["status", "published_at"] if new_status == JOB_STATUS_PUBLISHED else ["status"])
        if new_status == JOB_STATUS_PUBLISHED and not was_published:
            notify_job_published(job)
        messages.success(request, f"Job marked as {status_map[new_status]}.")
        return redirect("dashboard:home")
