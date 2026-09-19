from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, View

from core.constants import PAGE_SIZE
from core.permissions import JobSeekerRequiredMixin
from jobs.models import Job
from saved_jobs.models import SavedJob


class SavedJobsListView(JobSeekerRequiredMixin, ListView):
    model = SavedJob
    template_name = "saved_jobs/saved_job_list.html"
    context_object_name = "saved_jobs"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        return SavedJob.objects.filter(user=self.request.user).select_related("job", "job__company")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["saved_job_ids"] = {saved.job_id for saved in context["saved_jobs"]}
        return context


class ToggleSaveJobView(JobSeekerRequiredMixin, View):
    def post(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id)
        saved_job, created = SavedJob.objects.get_or_create(user=request.user, job=job)
        if created:
            is_saved = True
        else:
            saved_job.delete()
            is_saved = False

        if request.htmx:
            saved_job_ids = {job.pk} if is_saved else set()
            return render(request, "saved_jobs/_bookmark_button.html", {"job": job, "saved_job_ids": saved_job_ids})

        if is_saved:
            messages.success(request, "Job saved.")
        else:
            messages.info(request, "Job removed from your saved list.")
        next_url = request.POST.get("next") or "jobs:detail"
        if next_url == "jobs:detail":
            return redirect("jobs:detail", pk=job.pk)
        return redirect(next_url)
