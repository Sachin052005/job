"""Runs the ATS job-match engine against a submitted Application's resume
file, synchronously, right after the Application row is saved. This is
deliberately NOT in the request path that creates the Application itself -
call it only after application.save() has already succeeded, and never let
an exception here propagate: a parsing/analysis failure must never turn a
valid application into a lost one (spec: ATS must not break applications).
"""
import logging

from django.utils import timezone

from core.constants import ATS_STATUS_COMPLETE, ATS_STATUS_FAILED
from services.job_match_service import match_resume_to_job
from services.resume_parser_service import extract

logger = logging.getLogger(__name__)


def process_application_ats(application):
    try:
        parsed = extract(application.resume)
        if parsed.get("error"):
            raise ValueError(parsed["error"])

        candidate_skills = parsed.get("skills") or application.skills_list()
        result = match_resume_to_job(
            resume_text=parsed.get("text", ""),
            candidate_skills=candidate_skills,
            candidate_experience_years=application.experience_years,
            candidate_education_text=application.education_summary,
            candidate_location=application.location,
            candidate_title=application.current_title,
            projects_text="",
            job=application.job,
        )
    except Exception as exc:
        logger.exception("Application ATS processing failed for application_id=%s", application.pk)
        application.ats_status = ATS_STATUS_FAILED
        application.ats_error = "The resume could not be analyzed automatically."
        application.ats_processed_at = timezone.now()
        application.save(update_fields=["ats_status", "ats_error", "ats_processed_at"])
        return

    application.ats_status = ATS_STATUS_COMPLETE
    application.ats_score = result["compatibility_score"]
    application.ats_breakdown = result["analysis"]
    application.ats_error = ""
    application.ats_processed_at = timezone.now()
    application.save(update_fields=["ats_status", "ats_score", "ats_breakdown", "ats_error", "ats_processed_at"])

    from notifications.services import notify_ats_processing_complete

    notify_ats_processing_complete(application)
