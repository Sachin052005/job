"""Orchestration layer between the pure services (resume_parser_service,
resume_analysis_service, job_match_service) and the resumes app's models.
Nothing here computes a score itself - it only wires the deterministic
analysis into Resume/ResumeScan/ATSIssue/ResumeJobMatch, and is the single
place that decides when a resume needs re-parsing (spec: don't reparse an
unchanged resume on every page load).
"""
import logging

from django.utils import timezone

from core.constants import ANALYZER_VERSION, PARSE_STATUS_FAILED, PARSE_STATUS_PARSED, PARSER_VERSION
from services.job_match_service import match_resume_to_job
from services.resume_analysis_service import analyze
from services.resume_parser_service import extract

logger = logging.getLogger(__name__)


def ensure_parsed(resume, force=False):
    """Parse `resume.file` and cache the result on the Resume row, unless a
    fresh cached parse already exists for the current file/parser version.
    Never raises - a parse failure is recorded as parse_status=FAILED with
    the error stored (not shown as a raw traceback to the user) and the
    Resume row itself remains valid. Returns the (possibly cached) parsed
    dict, or {"error": ...} on failure."""
    if not force and not resume.needs_reparse():
        return dict(resume.parsed_data, text=resume.parsed_text)

    try:
        file_hash = resume.compute_file_hash()
        parsed = extract(resume.file)
    except Exception as exc:  # pragma: no cover - defensive, see module docstring
        logger.exception("Resume parse failed for resume_id=%s", resume.pk)
        resume.parse_status = PARSE_STATUS_FAILED
        resume.parse_error = "The resume could not be read. Please re-check the file and try again."
        resume.save(update_fields=["parse_status", "parse_error", "updated_at"])
        return {"error": resume.parse_error}

    if parsed.get("error"):
        resume.parse_status = PARSE_STATUS_FAILED
        resume.parse_error = parsed["error"]
        resume.file_hash = file_hash
        resume.save(update_fields=["parse_status", "parse_error", "file_hash", "updated_at"])
        return parsed

    resume.parse_status = PARSE_STATUS_PARSED
    resume.parse_error = ""
    resume.parsed_text = parsed.get("text", "")
    resume.parsed_data = {k: v for k, v in parsed.items() if k != "text"}
    resume.parser_version = PARSER_VERSION
    resume.file_hash = file_hash
    resume.parsed_at = timezone.now()
    resume.save(update_fields=[
        "parse_status", "parse_error", "parsed_text", "parsed_data",
        "parser_version", "file_hash", "parsed_at", "updated_at",
    ])
    return parsed


def _profile_skills_and_signals(student):
    """Pull the candidate-side signals used by resume_analysis_service and
    job_match_service from the student's existing Profile - never re-typed,
    never fabricated. Degrades gracefully if the profile is incomplete."""
    profile = getattr(student, "profile", None)
    if profile is None:
        return {}
    experience_records = list(profile.experience_records.all())
    project_texts = [p.description for p in profile.projects.all() if p.description]
    project_texts += [i.description for i in profile.internships.all() if i.description]
    project_texts += [e.description for e in experience_records if e.description]

    return {
        "profile_skills": profile.effective_skills_list(),
        "has_experience": bool(experience_records),
        "experience_years": profile.experience_years,
        "education_text": ", ".join(f"{e.degree} {e.institution}".strip() for e in profile.education_records.all()),
        "location": profile.location,
        "title": profile.headline,
        "projects_text": "\n".join(project_texts),
    }


def run_resume_scan(resume):
    """Parse (if needed) + analyze `resume`, store an immutable ResumeScan,
    and materialize its issues as ATSIssue rows for the Fix Center. Always
    creates a new ResumeScan - never overwrites a previous one (spec:
    analysis history)."""
    from resumes.models import ATSIssue, ResumeScan

    parsed = ensure_parsed(resume)
    signals = _profile_skills_and_signals(resume.student)
    result = analyze(
        parsed,
        profile_skills=signals.get("profile_skills"),
        has_professional_experience_elsewhere=signals.get("has_experience", False),
    )

    scan = ResumeScan.objects.create(
        resume=resume,
        score=result["score"],
        score_breakdown=result["score_breakdown"],
        extracted_data={
            "contact": parsed.get("contact", {}),
            "name": parsed.get("name", ""),
            "location": parsed.get("location", ""),
            "skills": parsed.get("skills", []),
            "sections_report": result.get("sections_report", {}),
            "grammar": result.get("grammar", {}),
            "page_count": parsed.get("page_count"),
            "has_images": parsed.get("has_images"),
            "has_tables": parsed.get("has_tables"),
            "multi_column": parsed.get("multi_column"),
        },
        issues=result["issues"],
        recommendations=result["recommendations"],
        analyzer_version=ANALYZER_VERSION,
    )

    parsed_text = resume.parsed_text or ""
    issue_rows = []
    for issue in result["issues"]:
        text = issue.get("text", "")
        start = end = None
        if text:
            idx = parsed_text.find(text)
            if idx != -1:
                start, end = idx, idx + len(text)
        issue_rows.append(ATSIssue(
            resume=resume, scan=scan, category=issue.get("category", "general"),
            severity=issue["priority"], section=issue.get("section", ""), text=text,
            start_position=start, end_position=end, message=issue["message"],
            suggestion=issue.get("suggestion", ""),
        ))
    if issue_rows:
        ATSIssue.objects.bulk_create(issue_rows)

    return scan


def run_job_match(resume, job=None, jd_text="", jd_title=""):
    """Match `resume` against either a real TalentPanda `job` posting or a
    freeform job description (pasted text, or text already extracted from an
    uploaded JD file - spec section 43), and store the result as a new
    ResumeJobMatch (never overwrites a previous match - spec: analysis
    history). Exactly one of `job` / `jd_text` is expected; the view is
    responsible for enforcing that."""
    from resumes.models import ResumeJobMatch

    parsed = ensure_parsed(resume)
    if parsed.get("error"):
        raise ValueError(parsed["error"])

    signals = _profile_skills_and_signals(resume.student)
    candidate_skills = parsed.get("skills", []) or signals.get("profile_skills", [])
    common_kwargs = dict(
        resume_text=resume.parsed_text,
        candidate_skills=candidate_skills,
        candidate_experience_years=signals.get("experience_years"),
        candidate_education_text=signals.get("education_text", ""),
        candidate_location=signals.get("location", ""),
        candidate_title=signals.get("title", ""),
        projects_text=signals.get("projects_text", ""),
    )

    if job is not None:
        result = match_resume_to_job(job=job, **common_kwargs)
    else:
        from services.skills_vocabulary import extract_skills

        result = match_resume_to_job(
            jd_title=jd_title, jd_description=jd_text,
            jd_required_skills=extract_skills(jd_text), **common_kwargs,
        )

    return ResumeJobMatch.objects.create(
        resume=resume, job=job, job_description_text="" if job is not None else jd_text,
        compatibility_score=result["compatibility_score"],
        matched_skills=result["matched_skills"],
        missing_skills=result["missing_skills"],
        analysis=result["analysis"],
    )


def score_trend(resume, limit=10):
    """Chronological (oldest first) list of {date, score} for the "Analysis
    History"/comparison views - built only from stored ResumeScan rows."""
    scans = list(resume.scans.order_by("created_at")[:limit])
    return [{"date": s.created_at, "score": s.score, "breakdown": s.score_breakdown} for s in scans]
