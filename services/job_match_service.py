"""Resume-vs-job ATS matching (spec: Job Matching / ATS Analysis). Local and
deterministic - TF-IDF + cosine similarity (scikit-learn) stands in for
"semantic"/keyword relevance instead of a paid embeddings API; everything
else is transparent keyword/rule-based comparison. Used both by the student
Resume Center (resumes.ResumeJobMatch) and the application-time ATS pipeline
(Application.ats_breakdown) so the two surfaces share one engine.
"""
from rapidfuzz import fuzz

from services.skill_match_service import calculate_skill_match


def _keyword_coverage(resume_text, job_keywords):
    if not job_keywords:
        return 100
    lower_text = (resume_text or "").lower()
    hits = sum(1 for kw in job_keywords if kw.lower() in lower_text)
    return round(hits / len(job_keywords) * 100)


def _content_similarity(resume_text, job_text):
    """TF-IDF cosine similarity between the resume and the job description +
    skills text. A lexical/keyword-relevance proxy, not a true embedding-based
    semantic score - labelled as "Keyword Relevance" in the UI so we never
    overclaim what this measures."""
    resume_text = (resume_text or "").strip()
    job_text = (job_text or "").strip()
    if not resume_text or not job_text:
        return 0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform([resume_text, job_text])
        similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
        return round(float(similarity) * 100)
    except ValueError:
        return 0


def _experience_match(candidate_experience_years, job_experience_min, job_experience_max):
    if job_experience_min is None and job_experience_max is None:
        return "n/a"
    if candidate_experience_years is None:
        return "unclear"
    if candidate_experience_years >= (job_experience_min or 0):
        return "meets"
    return "below"


def _education_match(candidate_education_text, job_education_required):
    if not job_education_required:
        return "n/a"
    if not candidate_education_text:
        return "unclear"
    return "meets" if fuzz.partial_ratio(job_education_required.lower(), candidate_education_text.lower()) >= 60 else "unclear"


def _location_match(candidate_location, job_location, is_remote):
    if is_remote:
        return "n/a"
    if not job_location:
        return "n/a"
    if not candidate_location:
        return "unclear"
    return "meets" if fuzz.partial_ratio(candidate_location.lower(), job_location.lower()) >= 55 else "different"


def _title_relevance(candidate_title, job_title):
    if not candidate_title or not job_title:
        return 0
    return round(fuzz.token_set_ratio(candidate_title, job_title))


def _project_relevance(projects_text, job_skills):
    if not projects_text or not job_skills:
        return 0
    lower_text = projects_text.lower()
    hits = sum(1 for skill in job_skills if skill.lower() in lower_text)
    return round(hits / len(job_skills) * 100)


def match_resume_to_job(*, resume_text, candidate_skills, candidate_experience_years=None,
                         candidate_education_text="", candidate_location="", candidate_title="",
                         projects_text="", job=None, jd_title="", jd_description="",
                         jd_required_skills=None, jd_experience_min=None, jd_experience_max=None,
                         jd_education_required_display="", jd_location="", jd_is_remote=False):
    """Compare a resume against either a real `job` (jobs.Job instance) or a
    freeform job description (pasted text / uploaded JD file, spec section
    43) - the two share this one engine so a TalentPanda job posting and an
    external JD are scored identically. For a freeform JD there is no
    reliable way to separate "required" from "preferred" skills from
    unstructured text, so every detected skill is treated as required and
    preferred-skill coverage is reported as n/a rather than guessed.

    Returns {compatibility_score, matched_skills, missing_skills, analysis}
    where `analysis` holds every component score/status shown in the UI - no
    single unexplained number (spec: transparent scoring)."""
    if job is not None:
        required_skills = job.skills_list()
        preferred_skills = job.preferred_skills_list()
        title = job.title
        experience_min, experience_max = job.experience_min, job.experience_max
        education_required_display = job.get_education_required_display() if job.education_required else ""
        location, is_remote = job.location, job.work_mode == "remote"
        job_text = " ".join(filter(None, [job.title, job.description, job.skills, job.preferred_skills]))
    else:
        required_skills = jd_required_skills or []
        preferred_skills = []
        title = jd_title
        experience_min, experience_max = jd_experience_min, jd_experience_max
        education_required_display = jd_education_required_display
        location, is_remote = jd_location, jd_is_remote
        job_text = " ".join(filter(None, [jd_title, jd_description]))

    required_match = calculate_skill_match(candidate_skills, required_skills)
    preferred_match = calculate_skill_match(candidate_skills, preferred_skills)

    experience_status = _experience_match(candidate_experience_years, experience_min, experience_max)
    education_status = _education_match(candidate_education_text, education_required_display)
    location_status = _location_match(candidate_location, location, is_remote)
    title_relevance = _title_relevance(candidate_title, title)
    project_relevance = _project_relevance(projects_text, required_skills)

    keyword_coverage = _keyword_coverage(resume_text, required_skills + preferred_skills)
    content_similarity = _content_similarity(resume_text, job_text)

    required_pct = required_match["percentage"] if required_match["percentage"] is not None else 100
    preferred_pct = preferred_match["percentage"] if preferred_match["percentage"] is not None else 100
    experience_bonus = 100 if experience_status in ("meets", "n/a") else (50 if experience_status == "unclear" else 0)
    education_bonus = 100 if education_status in ("meets", "n/a") else (50 if education_status == "unclear" else 0)

    compatibility_score = round(
        required_pct * 0.40
        + preferred_pct * 0.15
        + keyword_coverage * 0.15
        + content_similarity * 0.15
        + experience_bonus * 0.10
        + education_bonus * 0.05
    )
    compatibility_score = max(0, min(100, compatibility_score))

    analysis = {
        "jd_title": title,
        "required_skills_percent": required_match["percentage"],
        "preferred_skills_percent": preferred_match["percentage"],
        "matched_required_skills": required_match["matched_skills"],
        "missing_required_skills": required_match["unmatched_skills"],
        "matched_preferred_skills": preferred_match["matched_skills"],
        "missing_preferred_skills": preferred_match["unmatched_skills"],
        "experience_match": experience_status,
        "education_match": education_status,
        "location_match": location_status,
        "job_title_relevance_percent": title_relevance,
        "project_relevance_percent": project_relevance,
        "keyword_coverage_percent": keyword_coverage,
        "keyword_relevance_percent": content_similarity,
    }

    return {
        "compatibility_score": compatibility_score,
        "matched_skills": required_match["matched_skills"],
        "missing_skills": required_match["unmatched_skills"],
        "analysis": analysis,
    }
