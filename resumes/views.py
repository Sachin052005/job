from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView, View

from core.permissions import JobSeekerRequiredMixin
from resumes.forms import JobMatchForm, ResumeRenameForm, ResumeUploadForm
from resumes.models import ATSIssue, Resume
from services.resume_parser_service import extract
from services.resume_service import run_job_match, run_resume_scan


class OwnResumeMixin(JobSeekerRequiredMixin):
    """Every resumes view is scoped to request.user's own resumes - a
    student can never reach another student's resume/scan/issue by
    guessing an id (spec: IDOR protection)."""

    def get_queryset(self):
        return Resume.objects.filter(student=self.request.user)


class ResumeListView(OwnResumeMixin, ListView):
    """Doubles as the entry point for both ATS modes (spec sections 32-34/41-43):
    ?mode=job_match changes the page's intro/CTA text and routes every resume's
    action straight to its Job Match tab instead of the Resume Health overview -
    a real difference in destination, not a relabeled button."""

    template_name = "resumes/resume_list.html"
    context_object_name = "resumes"

    def get_queryset(self):
        return super().get_queryset().select_related().prefetch_related("scans")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["mode"] = "job_match" if self.request.GET.get("mode") == "job_match" else "check"
        return context


class ResumeUploadView(OwnResumeMixin, CreateView):
    form_class = ResumeUploadForm
    template_name = "resumes/resume_upload.html"

    def form_valid(self, form):
        form.instance.student = self.request.user
        form.instance.is_primary = not Resume.objects.filter(student=self.request.user).exists()
        response = super().form_valid(form)
        try:
            run_resume_scan(self.object)
        except Exception:
            # The resume row itself is already saved and valid either way -
            # a scan failure here never loses the upload (spec: ATS must
            # not break the underlying feature it's attached to).
            messages.warning(self.request, "Resume uploaded, but the initial scan could not be completed. You can retry from the resume page.")
        else:
            messages.success(self.request, "Resume uploaded and scanned.")
        return response

    def get_success_url(self):
        url = reverse("resumes:detail", kwargs={"pk": self.object.pk})
        if self.request.GET.get("mode") == "job_match":
            url = f"{url}?tab=job_match"
        return url


class ResumeDetailView(OwnResumeMixin, DetailView):
    template_name = "resumes/resume_detail.html"
    context_object_name = "resume"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("scans", "job_matches__job__company")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resume = self.object
        latest_scan = resume.scans.first()
        previous_scan = resume.scans.all()[1] if resume.scans.count() > 1 else None

        context["latest_scan"] = latest_scan
        context["previous_scan"] = previous_scan
        context["score_delta"] = (latest_scan.score - previous_scan.score) if (latest_scan and previous_scan) else None
        context["open_issues"] = (
            ATSIssue.objects.filter(resume=resume, scan=latest_scan).exclude(status="ignored")
            if latest_scan else ATSIssue.objects.none()
        )
        context["issues_by_severity"] = {
            "high": context["open_issues"].filter(severity="high"),
            "medium": context["open_issues"].filter(severity="medium"),
            "low": context["open_issues"].filter(severity="low"),
        }
        context["score_history"] = list(resume.scans.order_by("created_at").values("created_at", "score", "score_breakdown"))
        context["latest_match"] = resume.job_matches.select_related("job", "job__company").first()
        context["job_match_form"] = JobMatchForm()
        context["tab"] = self.request.GET.get("tab", "overview")
        return context


class ResumeScanView(OwnResumeMixin, View):
    def post(self, request, pk):
        resume = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            scan = run_resume_scan(resume)
        except Exception:
            messages.error(request, "The resume scan could not be completed. Your resume is safe - please try again.")
        else:
            previous = resume.scans.exclude(pk=scan.pk).first()
            if previous:
                delta = scan.score - previous.score
                sign = "+" if delta >= 0 else ""
                messages.success(request, f"Resume re-scanned. ATS Score: {previous.score} -> {scan.score} ({sign}{delta}).")
            else:
                messages.success(request, f"Resume scanned. ATS Score: {scan.score}.")
        return redirect("resumes:detail", pk=pk)


class ResumeJobMatchView(OwnResumeMixin, View):
    """Runs Job Match ATS Check against whichever of the three JD sources the
    student supplied (spec section 43): an existing TalentPanda job, pasted
    text, or an uploaded PDF/DOCX (parsed with the same resume text
    extractor - a job description is just another document to read text
    from)."""

    def post(self, request, pk):
        resume = get_object_or_404(self.get_queryset(), pk=pk)
        form = JobMatchForm(request.POST, request.FILES)
        if not form.is_valid():
            for error in form.non_field_errors():
                messages.error(request, error)
            return redirect(f"{reverse('resumes:detail', kwargs={'pk': pk})}?tab=job_match")

        job = form.cleaned_data.get("job")
        jd_file = form.cleaned_data.get("jd_file")
        pasted_text = form.cleaned_data.get("pasted_text", "").strip()

        try:
            if job:
                run_job_match(resume, job=job)
            elif jd_file:
                parsed_jd = extract(jd_file)
                if parsed_jd.get("error"):
                    raise ValueError(parsed_jd["error"])
                run_job_match(resume, jd_text=parsed_jd.get("text", ""), jd_title=jd_file.name.rsplit(".", 1)[0])
            else:
                run_job_match(resume, jd_text=pasted_text, jd_title="Pasted Job Description")
        except Exception:
            messages.error(request, "Job match could not be completed. Please check the job description and try again.")
        else:
            messages.success(request, "Job match complete.")
        return redirect(f"{reverse('resumes:detail', kwargs={'pk': pk})}?tab=job_match")


class ResumeIssueStatusView(OwnResumeMixin, View):
    def post(self, request, pk, issue_id):
        resume = get_object_or_404(self.get_queryset(), pk=pk)
        issue = get_object_or_404(ATSIssue, pk=issue_id, resume=resume)
        new_status = request.POST.get("status")
        if new_status in {"open", "fixed", "ignored"}:
            issue.status = new_status
            issue.save(update_fields=["status", "updated_at"])
        return redirect(f"{reverse('resumes:detail', kwargs={'pk': pk})}?tab=fixes")


class ResumeRenameView(OwnResumeMixin, UpdateView):
    form_class = ResumeRenameForm
    template_name = "resumes/resume_rename.html"

    def get_success_url(self):
        messages.success(self.request, "Resume renamed.")
        return reverse("resumes:detail", kwargs={"pk": self.object.pk})


class ResumeDuplicateView(OwnResumeMixin, View):
    def post(self, request, pk):
        original = get_object_or_404(self.get_queryset(), pk=pk)
        from django.core.files.base import ContentFile

        original.file.seek(0)
        duplicate = Resume.objects.create(
            student=request.user,
            title=f"{original.title} (Copy)",
            file=ContentFile(original.file.read(), name=original.file.name.rsplit("/", 1)[-1]),
        )
        messages.success(request, f'Duplicated as "{duplicate.title}". Run a scan to analyze it.')
        return redirect("resumes:detail", pk=duplicate.pk)


class ResumeSetPrimaryView(OwnResumeMixin, View):
    def post(self, request, pk):
        resume = get_object_or_404(self.get_queryset(), pk=pk)
        Resume.objects.filter(student=request.user, is_primary=True).update(is_primary=False)
        resume.is_primary = True
        resume.save(update_fields=["is_primary", "updated_at"])
        messages.success(request, f'"{resume.title}" is now your primary resume.')
        return redirect("resumes:list")


class ResumeDeleteView(OwnResumeMixin, DeleteView):
    template_name = "resumes/resume_confirm_delete.html"

    def get_success_url(self):
        messages.success(self.request, "Resume deleted.")
        return reverse("resumes:list")


class ResumeDownloadView(OwnResumeMixin, View):
    def get(self, request, pk):
        resume = get_object_or_404(self.get_queryset(), pk=pk)
        if not resume.file:
            raise Http404("No file available.")
        return FileResponse(resume.file.open("rb"), as_attachment=True, filename=resume.file.name.rsplit("/", 1)[-1])
