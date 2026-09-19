"""Application-layer helpers that sit on top of the pure `services.ats_service`
analysis functions - specifically, computing and persisting a compact ATS
match snapshot on an Application so it isn't recomputed on every page view.
"""
from django.utils import timezone

from services.ats_service import analyze_job_match, extract_resume_text


def build_match_snapshot(match_result, resume_marker, job_id):
    return {
        "overall_percent": match_result["overall_percent"],
        "components": {
            key: {"label": value["label"], "percent": value["percent"], "reason": value["reason"]}
            for key, value in match_result["components"].items()
        },
        "matched_skills": match_result["matched_skills"],
        "missing_skills": match_result["missing_skills"],
        "matched_keywords": match_result["matched_keywords"][:15],
        "missing_keywords": match_result["missing_keywords"][:15],
        "disclaimer": match_result["disclaimer"],
        "computed_at": timezone.now().isoformat(),
        "resume_marker": resume_marker,
        "job_id": job_id,
    }


def ensure_match_snapshot(application, job=None):
    """Return a compact ATS match snapshot for this application, computing and
    persisting it only if the resume file or job has changed since the last
    computation. Uses `Application.objects.filter(...).update(...)` so it
    never touches `updated_at` or triggers save-related side effects.
    """
    job = job or application.job
    resume_marker = application.resume.name or ""
    existing = application.match_snapshot or {}
    if existing.get("resume_marker") == resume_marker and existing.get("job_id") == job.pk:
        return existing

    resume_text, resume_error = extract_resume_text(application.resume)
    match_result = analyze_job_match(application.applicant.profile, resume_text, job, resume_error)
    snapshot = build_match_snapshot(match_result, resume_marker, job.pk)

    application.match_snapshot = snapshot
    type(application).objects.filter(pk=application.pk).update(match_snapshot=snapshot)
    return snapshot
