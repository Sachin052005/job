"""Deterministic, non-AI skill matching between a candidate's skills and a
job's required skills (Job Skill Match feature).

No ML/LLM/Ollama involved anywhere in this module - just normalization
(core.utils.normalize_skill / SKILL_ALIASES) and set comparison. The result
is reproducible: the same two skill lists always produce the same
percentage, matched list, and unmatched list.
"""
from core.utils import normalize_skill


def _normalize_list(raw_skills):
    """Trim/lower/alias-normalize a list (or comma-separated string) of skills.

    Removes blanks and duplicates (case-insensitive) while preserving the
    first-seen display form and the original order.
    """
    if not raw_skills:
        return []
    if isinstance(raw_skills, str):
        items = raw_skills.split(",")
    else:
        items = raw_skills

    seen = set()
    normalized = []
    for item in items:
        if item is None:
            continue
        skill = normalize_skill(str(item))
        if not skill:
            continue
        key = skill.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(skill)
    return normalized


def calculate_skill_match(candidate_skills, required_job_skills):
    """Compare candidate skills against a job's required skills.

    Both arguments accept either a comma-separated string or an iterable of
    skill strings. Matching is exact after normalization (case-insensitive,
    whitespace-trimmed, alias-mapped) - no fuzzy/partial matching, so it
    never produces a misleading match.

    Formula (spec section 6):
        percentage = round(matched_required_count / total_required_count * 100)

    Extra candidate skills that aren't required by the job never increase
    the percentage (spec section 19.C) - only required skills are counted.

    Returns:
        {
            "percentage": int | None,   # None means "no required skills" (job posted without skills)
            "matched_skills": [...],    # required skills the candidate has, in job order
            "unmatched_skills": [...],  # required skills the candidate is missing, in job order
            "candidate_skills": [...],  # normalized, deduplicated candidate skills
            "job_skills": [...],        # normalized, deduplicated required job skills
        }
    """
    candidate = _normalize_list(candidate_skills)
    required = _normalize_list(required_job_skills)

    candidate_keys = {skill.lower() for skill in candidate}

    matched = [skill for skill in required if skill.lower() in candidate_keys]
    unmatched = [skill for skill in required if skill.lower() not in candidate_keys]

    if not required:
        percentage = None
    else:
        percentage = round(len(matched) / len(required) * 100)

    return {
        "percentage": percentage,
        "matched_skills": matched,
        "unmatched_skills": unmatched,
        "candidate_skills": candidate,
        "job_skills": required,
    }
