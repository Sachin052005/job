"""Local, free, rule-based ATS (Applicant Tracking) analysis.

No paid API is used anywhere in this module. Resume text extraction is done
with PyMuPDF (PDF) and python-docx (DOCX); GitHub analysis uses GitHub's
public REST API (no token, fixed host, short timeout); LinkedIn is never
scraped - only the URL is validated.

Every function here is designed to fail gracefully: a bad file, an
unreachable host, or malformed input should return a clear "unavailable" /
"not detected" result, never raise and never break the calling view.
"""
import re
from urllib.parse import urlparse

import requests
from django.core.cache import cache

from core.constants import ATS_MATCH_DISCLAIMER, ATS_WEIGHTS

# ---------------------------------------------------------------------------
# Skill normalization
# ---------------------------------------------------------------------------

# Maintainable alias table: raw term (lowercase) -> canonical display name.
# Only genuinely equivalent terms are mapped here - never loosely related ones.
SKILL_ALIASES = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "reactjs": "React",
    "react.js": "React",
    "react": "React",
    "vuejs": "Vue.js",
    "vue": "Vue.js",
    "nodejs": "Node.js",
    "node": "Node.js",
    "node.js": "Node.js",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "psql": "PostgreSQL",
    "mysql": "MySQL",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "restful api": "REST API",
    "restful apis": "REST API",
    "rest api": "REST API",
    "rest apis": "REST API",
    "drf": "Django REST Framework",
    "django rest framework": "Django REST Framework",
    "django-rest-framework": "Django REST Framework",
    "html5": "HTML",
    "html": "HTML",
    "css3": "CSS",
    "css": "CSS",
    "py": "Python",
    "python3": "Python",
    "python": "Python",
    "django": "Django",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "Google Cloud Platform",
    "google cloud": "Google Cloud Platform",
    "azure": "Azure",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "redis": "Redis",
    "git": "Git",
    "github": "GitHub",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
}


def normalize_skill(raw):
    key = raw.strip().lower()
    return SKILL_ALIASES.get(key, raw.strip())


def normalize_skills(raw_skills):
    """De-duplicated, alias-normalized skill list, order-preserving."""
    seen = set()
    normalized = []
    for raw in raw_skills:
        if not raw or not raw.strip():
            continue
        canon = normalize_skill(raw)
        key = canon.lower()
        if key not in seen:
            seen.add(key)
            normalized.append(canon)
    return normalized


# ---------------------------------------------------------------------------
# Resume text extraction
# ---------------------------------------------------------------------------

RESUME_CACHE_TTL_SECONDS = 60 * 60  # 1 hour
GITHUB_CACHE_TTL_SECONDS = 60 * 60  # 1 hour


def extract_resume_text(file_field):
    """Extract plain text from a resume FileField. Never raises.

    Returns (text, error_message). error_message is empty on success.
    """
    if not file_field:
        return "", "No resume file is available."

    name = getattr(file_field, "name", "") or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    cache_key = f"ats:resume_text:{name}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, ""

    try:
        file_field.open("rb")
        try:
            data = file_field.read()
        finally:
            file_field.close()
    except Exception:
        return "", "Resume file could not be opened."

    text = ""
    error = ""
    try:
        if ext == "pdf":
            text = _extract_pdf_text(data)
        elif ext == "docx":
            text = _extract_docx_text(data)
        elif ext == "txt":
            text = data.decode("utf-8", errors="ignore")
        elif ext == "doc":
            error = "Legacy .doc files cannot be parsed automatically. Please re-save as PDF or DOCX for automatic analysis."
        else:
            error = "Unsupported resume format for automatic analysis."
    except Exception:
        text = ""
        error = "Resume text could not be extracted automatically. The file may be corrupted or image-only."

    if not error and not text.strip():
        error = "Resume text could not be extracted automatically. The file may be image-only or unreadable."

    if text:
        cache.set(cache_key, text, RESUME_CACHE_TTL_SECONDS)
    return text, error


def _extract_pdf_text(data):
    import pymupdf

    text_parts = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def _extract_docx_text(data):
    import io

    import docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


# ---------------------------------------------------------------------------
# Resume section / content analysis
# ---------------------------------------------------------------------------

_SECTION_PATTERNS = {
    "Contact Information": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|(\+?\d[\d\-\s()]{7,}\d)"),
    "Professional Summary": re.compile(r"\b(summary|profile|objective|about me)\b", re.I),
    "Skills": re.compile(r"\b(skills|technical skills|technologies)\b", re.I),
    "Education": re.compile(
        r"\b(education|b\.?tech|m\.?tech|bachelor|master|b\.?sc|m\.?sc|university|college|degree)\b", re.I
    ),
    "Experience": re.compile(r"\b(experience|employment|work history|internship)\b", re.I),
    "Projects": re.compile(r"\b(projects?)\b", re.I),
    "LinkedIn": re.compile(r"linkedin\.com/in/[\w-]+", re.I),
    "GitHub": re.compile(r"github\.com/[\w-]+", re.I),
}

_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "are", "that", "this", "will",
    "our", "have", "from", "who", "they", "team", "role", "job", "work",
    "including", "able", "must", "not", "can", "all", "any", "such", "into",
    "per", "using", "use", "years", "year", "experience", "preferred",
    "required", "requirements", "responsibilities", "about", "company", "etc",
}


def detect_resume_sections(text):
    """Return {section_name: bool_detected} for the standard ATS section checklist."""
    return {name: bool(pattern.search(text)) for name, pattern in _SECTION_PATTERNS.items()}


def analyze_resume_text(text, extraction_error=""):
    """Produce a professional ATS resume readiness report from raw resume text."""
    if extraction_error or not text.strip():
        return {
            "readiness_percent": 0,
            "sections": {name: False for name in _SECTION_PATTERNS},
            "issues": [extraction_error or "Resume text is empty."],
            "suggestions": [
                "Upload a text-based PDF or DOCX resume so it can be automatically analyzed.",
            ],
            "word_count": 0,
        }

    sections = detect_resume_sections(text)
    detected_count = sum(1 for v in sections.values() if v)
    readiness_percent = int((detected_count / len(sections)) * 100)

    words = re.findall(r"[A-Za-z][A-Za-z+.#-]*", text)
    word_count = len(words)

    issues = []
    suggestions = []

    if word_count < 120:
        issues.append("Resume content appears extremely short for automatic analysis.")
        suggestions.append("Expand your resume with more detail on skills, projects, and experience.")

    word_counts = {}
    for w in words:
        wl = w.lower()
        if len(wl) > 3 and wl not in _STOPWORDS:
            word_counts[wl] = word_counts.get(wl, 0) + 1
    repeated = [w for w, c in word_counts.items() if c >= 12]
    if repeated:
        issues.append("Some words appear to be repeated excessively, which may hurt readability.")

    if not sections["Contact Information"]:
        issues.append("No email address or phone number was detected.")
        suggestions.append("Add a clear email address and phone number near the top of your resume.")
    if not sections["Professional Summary"]:
        suggestions.append("Add a concise professional summary near the top of your resume.")
    if not sections["Skills"]:
        issues.append("A dedicated skills section was not detected.")
        suggestions.append("Add a clearly labeled 'Skills' section listing 3-5+ relevant technical skills.")
    if not sections["Education"]:
        suggestions.append("Add an 'Education' section with your degree and institution.")
    if not sections["Experience"] and not sections["Projects"]:
        suggestions.append("Add an 'Experience' or 'Projects' section describing what you built or worked on.")
    if sections["Experience"] or sections["Projects"]:
        if not re.search(r"\b\d+%|\b\d+x\b|\$\d|\b\d{2,}\+?\s*(users|requests|records|rows)\b", text, re.I):
            suggestions.append("Add measurable achievements to your project/experience descriptions (numbers, %, scale).")
    if not sections["LinkedIn"]:
        suggestions.append("Add your LinkedIn profile URL to your resume.")
    if not sections["GitHub"]:
        suggestions.append("Add your GitHub profile URL to your resume.")

    return {
        "readiness_percent": readiness_percent,
        "sections": sections,
        "issues": issues,
        "suggestions": suggestions,
        "word_count": word_count,
    }


# ---------------------------------------------------------------------------
# Skill / keyword comparison
# ---------------------------------------------------------------------------


def compare_skills(candidate_skills, job_skills):
    """Compare two raw skill lists (already comma-split). Returns matched/missing/percent."""
    candidate_norm = {s.lower() for s in normalize_skills(candidate_skills)}
    job_norm = normalize_skills(job_skills)

    matched = [s for s in job_norm if s.lower() in candidate_norm]
    missing = [s for s in job_norm if s.lower() not in candidate_norm]

    percent = 100 if not job_norm else int((len(matched) / len(job_norm)) * 100)
    return {"matched": matched, "missing": missing, "percent": percent, "total_required": len(job_norm)}


def extract_keywords(text, limit=25):
    """Significant, deduplicated keywords from free text (title-cased words/phrases)."""
    words = re.findall(r"[A-Za-z][A-Za-z+.#-]{2,}", text)
    seen = []
    seen_lower = set()
    for w in words:
        wl = w.lower()
        if wl in _STOPWORDS or wl in seen_lower:
            continue
        seen_lower.add(wl)
        seen.append(normalize_skill(w))
        if len(seen) >= limit:
            break
    return seen


def compare_keywords(resume_text, job_text):
    job_keywords = extract_keywords(job_text)
    resume_lower = resume_text.lower()
    matched = [k for k in job_keywords if k.lower() in resume_lower]
    missing = [k for k in job_keywords if k.lower() not in resume_lower]
    percent = 100 if not job_keywords else int((len(matched) / len(job_keywords)) * 100)
    return {"matched": matched, "missing": missing, "percent": percent}


# ---------------------------------------------------------------------------
# Experience / education comparison
# ---------------------------------------------------------------------------


def compare_experience(candidate_years, job_experience_min):
    job_experience_min = job_experience_min or 0
    if job_experience_min <= 0:
        return {
            "percent": 100,
            "reason": "This job does not specify a minimum experience requirement.",
        }
    if candidate_years >= job_experience_min:
        return {
            "percent": 100,
            "reason": f"Your profile lists {candidate_years} year(s) of experience, meeting the {job_experience_min}+ year requirement.",
        }
    if candidate_years >= max(0, job_experience_min - 1):
        return {
            "percent": 60,
            "reason": f"Your profile lists {candidate_years} year(s) of experience, close to the {job_experience_min}+ year requirement.",
        }
    percent = int(max(0, min(100, (candidate_years / job_experience_min) * 100))) if job_experience_min else 100
    return {
        "percent": percent,
        "reason": f"Your profile lists {candidate_years} year(s) of experience against a {job_experience_min}+ year requirement.",
    }


def evaluate_education_signal(resume_text):
    detected = bool(_SECTION_PATTERNS["Education"].search(resume_text)) if resume_text else False
    if detected:
        return {"percent": 100, "reason": "An education section was detected in the submitted resume."}
    return {
        "percent": 50,
        "reason": "An education section was not clearly detected. This does not necessarily mean the requirement isn't met - please review manually.",
    }


# ---------------------------------------------------------------------------
# Job requirement extraction
# ---------------------------------------------------------------------------


def extract_job_requirements(job):
    return {
        "skills": normalize_skills(job.skills_list()),
        "experience_min": job.experience_min or 0,
        "text": f"{job.title}\n{job.description}\n{job.responsibilities}",
    }


# ---------------------------------------------------------------------------
# Overall job match
# ---------------------------------------------------------------------------


def analyze_job_match(profile, resume_text, job, resume_error=""):
    """Weighted, explainable match between a candidate profile/resume and a job.

    Never claims to predict hiring outcomes - see ATS_MATCH_DISCLAIMER.
    """
    requirements = extract_job_requirements(job)

    skills_cmp = compare_skills(profile.skills_list(), requirements["skills"])
    experience_cmp = compare_experience(profile.experience_years, requirements["experience_min"])
    education_cmp = evaluate_education_signal(resume_text)
    keyword_cmp = compare_keywords(resume_text or profile.summary, requirements["text"])
    resume_analysis = analyze_resume_text(resume_text, resume_error)

    components = {
        "skills": {
            "label": "Skills Match",
            "percent": skills_cmp["percent"],
            "reason": (
                f"{len(skills_cmp['matched'])} of {skills_cmp['total_required']} job skill(s) were detected in your profile."
                if requirements["skills"]
                else "This job does not list specific required skills."
            ),
        },
        "experience": {"label": "Experience Match", "percent": experience_cmp["percent"], "reason": experience_cmp["reason"]},
        "education": {"label": "Education Match", "percent": education_cmp["percent"], "reason": education_cmp["reason"]},
        "keyword": {
            "label": "Keyword Match",
            "percent": keyword_cmp["percent"],
            "reason": f"{len(keyword_cmp['matched'])} of {len(keyword_cmp['matched']) + len(keyword_cmp['missing'])} major job-description keyword(s) were detected.",
        },
        "resume_completeness": {
            "label": "Resume Completeness",
            "percent": resume_analysis["readiness_percent"],
            "reason": "Based on how many standard resume sections were detected.",
        },
    }

    overall = sum(components[k]["percent"] * (ATS_WEIGHTS[k] / 100) for k in ATS_WEIGHTS)

    return {
        "overall_percent": round(overall),
        "components": components,
        "weights": ATS_WEIGHTS,
        "matched_skills": skills_cmp["matched"],
        "missing_skills": skills_cmp["missing"],
        "matched_keywords": keyword_cmp["matched"],
        "missing_keywords": keyword_cmp["missing"],
        "resume_analysis": resume_analysis,
        "disclaimer": ATS_MATCH_DISCLAIMER,
    }


def generate_resume_suggestions(match_result):
    """Resume-improvement suggestions grounded only in detected content - never invents skills."""
    suggestions = list(match_result["resume_analysis"]["suggestions"])
    missing = match_result["missing_skills"][:5]
    if missing:
        suggestions.append(
            "Consider mentioning these job-relevant skills if you truthfully have experience with them: "
            + ", ".join(missing)
            + "."
        )
    return suggestions


# ---------------------------------------------------------------------------
# GitHub public-data analysis (no API key)
# ---------------------------------------------------------------------------

_GITHUB_URL_RE = re.compile(r"^https?://(www\.)?github\.com/(?P<username>[A-Za-z0-9-]+)/?$", re.I)
_GITHUB_API_HOST = "https://api.github.com"


def parse_github_username(github_url):
    if not github_url:
        return None
    match = _GITHUB_URL_RE.match(github_url.strip())
    return match.group("username") if match else None


def analyze_github_profile(github_url, job_skills=None):
    """Best-effort, no-token analysis of a public GitHub profile. Never raises.

    The network fetch is cached per-username (job-agnostic); job-relevant
    repository matching is recomputed on top of the cached data for whichever
    job is currently being viewed.
    """
    username = parse_github_username(github_url)
    if not username:
        return {"status": "invalid_url", "url": github_url}

    cache_key = f"ats:github:{username.lower()}"
    base = cache.get(cache_key)
    if base is None:
        base = _fetch_github_analysis(username, github_url)
        cache.set(cache_key, base, GITHUB_CACHE_TTL_SECONDS)

    result = {k: v for k, v in base.items() if k != "_repo_summaries"}
    if base.get("status") == "available":
        result["relevant_repositories"] = _find_relevant_repositories(
            base.get("_repo_summaries", []), job_skills
        )
    return result


def _fetch_github_analysis(username, github_url):
    """Job-agnostic GitHub fetch: repo count + detected technologies + a
    compact per-repo summary (used later for job-relevant matching)."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "NammaCareer-ATS"}
    try:
        response = requests.get(
            f"{_GITHUB_API_HOST}/users/{username}/repos",
            params={"per_page": 30, "sort": "updated"},
            headers=headers,
            timeout=5,
        )
    except requests.RequestException:
        return {"status": "unavailable", "url": github_url, "username": username}

    if response.status_code == 404:
        return {"status": "not_found", "url": github_url, "username": username}
    if response.status_code == 403:
        return {"status": "rate_limited", "url": github_url, "username": username}
    if response.status_code != 200:
        return {"status": "unavailable", "url": github_url, "username": username}

    try:
        repos = response.json()
        if not isinstance(repos, list):
            return {"status": "unavailable", "url": github_url, "username": username}
    except ValueError:
        return {"status": "unavailable", "url": github_url, "username": username}

    detected_technologies = set()
    repo_summaries = []

    for repo in repos:
        if not isinstance(repo, dict):
            continue
        language = repo.get("language")
        haystack = " ".join(
            str(repo.get(field) or "") for field in ("name", "description")
        ) + " " + " ".join(repo.get("topics") or [])
        for alias, canon in SKILL_ALIASES.items():
            if alias in haystack.lower():
                detected_technologies.add(canon)
        if language:
            detected_technologies.add(normalize_skill(language))
        repo_summaries.append({"name": repo.get("name"), "language": language, "haystack": haystack.lower()})

    return {
        "status": "available",
        "url": github_url,
        "username": username,
        "repository_count": len(repos),
        "detected_technologies": sorted(detected_technologies),
        "_repo_summaries": repo_summaries,
    }


def _find_relevant_repositories(repo_summaries, job_skills):
    job_skill_set = {s.lower() for s in normalize_skills(job_skills or [])}
    if not job_skill_set:
        return []
    relevant = []
    for summary in repo_summaries:
        language = summary.get("language")
        is_relevant = (language and normalize_skill(language).lower() in job_skill_set) or any(
            skill in summary.get("haystack", "") for skill in job_skill_set
        )
        if is_relevant:
            relevant.append(summary.get("name"))
    return relevant[:5]


# ---------------------------------------------------------------------------
# LinkedIn (validation only, no scraping)
# ---------------------------------------------------------------------------

_LINKEDIN_HOST_RE = re.compile(r"^(www\.)?linkedin\.com$", re.I)


def analyze_linkedin_url(linkedin_url):
    """LinkedIn is never scraped. Validate the URL and hand back to the human reviewer."""
    if not linkedin_url:
        return {"status": "not_provided"}
    host = (urlparse(linkedin_url).hostname or "").lower()
    if not _LINKEDIN_HOST_RE.match(host):
        return {"status": "invalid_url", "url": linkedin_url}
    return {"status": "manual_review", "url": linkedin_url}


# ---------------------------------------------------------------------------
# External profile status summary (for UI status chips)
# ---------------------------------------------------------------------------


def external_profile_status(url, kind):
    if not url:
        return "not_provided"
    if kind == "github":
        analysis = analyze_github_profile(url)
        return {
            "available": "available",
            "not_found": "could_not_verify",
            "rate_limited": "could_not_verify",
            "unavailable": "could_not_verify",
            "invalid_url": "could_not_verify",
        }.get(analysis.get("status"), "could_not_verify")
    if kind == "linkedin":
        return "available" if analyze_linkedin_url(url).get("status") == "manual_review" else "could_not_verify"
    return "available"
