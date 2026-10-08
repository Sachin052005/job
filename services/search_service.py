from django.db.models import Q

from core.constants import JOB_STATUS_PUBLISHED, ROLE_JOB_SEEKER

TRUTHY_PARAM_VALUES = {"1", "true", "yes", "on"}


def filter_jobs(queryset, params):
    """Apply keyword/location/category/employment-type/experience/salary filters to a Job queryset."""
    queryset = queryset.filter(status=JOB_STATUS_PUBLISHED)

    keyword = (params.get("keyword") or "").strip()
    if keyword:
        queryset = queryset.filter(
            Q(title__icontains=keyword)
            | Q(skills__icontains=keyword)
            | Q(company__name__icontains=keyword)
        )

    location = (params.get("location") or "").strip()
    if location:
        queryset = queryset.filter(location__icontains=location)

    domain = (params.get("domain") or "").strip()
    if domain:
        queryset = queryset.filter(domain__slug=domain)

    subdomain = (params.get("subdomain") or "").strip()
    if subdomain:
        queryset = queryset.filter(subdomain__slug=subdomain)

    employment_type = (params.get("employment_type") or "").strip()
    if employment_type:
        queryset = queryset.filter(employment_type=employment_type)

    experience = params.get("experience")
    if experience not in (None, ""):
        try:
            queryset = queryset.filter(experience_min__lte=int(experience))
        except (TypeError, ValueError):
            pass

    salary_min = params.get("salary_min")
    if salary_min not in (None, ""):
        try:
            value = int(salary_min)
            queryset = queryset.filter(Q(salary_max__gte=value) | Q(salary_max__isnull=True))
        except (TypeError, ValueError):
            pass

    def _truthy(value):
        return str(value).strip().lower() in TRUTHY_PARAM_VALUES

    if _truthy(params.get("freshers_only")):
        queryset = queryset.filter(Q(badges__icontains="freshers_can_apply") | Q(experience_min=0))
    if _truthy(params.get("remote_only")):
        queryset = queryset.filter(Q(work_mode="remote") | Q(badges__icontains="remote"))
    if _truthy(params.get("urgent_only")):
        queryset = queryset.filter(badges__icontains="urgent_hiring")
    if _truthy(params.get("walkin_only")):
        queryset = queryset.filter(badges__icontains="walkin_interview")
    work_mode = (params.get("work_mode") or "").strip()
    if work_mode:
        queryset = queryset.filter(work_mode=work_mode)

    return queryset.select_related("company", "domain", "subdomain").distinct()


def filter_applications(queryset, params):
    """Apply HR-facing search/filters to an Application queryset.

    All filters are transparent and job-related: candidate name/email/skills
    keyword, application status, and resume/LinkedIn/GitHub availability.
    Never filters candidates out based on protected characteristics.
    """
    keyword = (params.get("keyword") or "").strip()
    if keyword:
        queryset = queryset.filter(
            Q(applicant__first_name__icontains=keyword)
            | Q(applicant__last_name__icontains=keyword)
            | Q(applicant__username__icontains=keyword)
            | Q(applicant__email__icontains=keyword)
            | Q(applicant__profile__skills__icontains=keyword)
        )

    status = (params.get("status") or "").strip()
    if status:
        queryset = queryset.filter(status=status)

    min_experience = params.get("min_experience")
    if min_experience not in (None, ""):
        try:
            queryset = queryset.filter(applicant__profile__experience_years__gte=int(min_experience))
        except (TypeError, ValueError):
            pass

    def _truthy(value):
        return str(value).strip().lower() in TRUTHY_PARAM_VALUES

    if _truthy(params.get("has_resume")):
        queryset = queryset.exclude(resume="")
    if _truthy(params.get("has_linkedin")):
        queryset = queryset.exclude(applicant__profile__linkedin_url="")
    if _truthy(params.get("has_github")):
        queryset = queryset.exclude(applicant__profile__github_url="")
    if _truthy(params.get("fresher_only")):
        queryset = queryset.filter(experience_years=0)

    ats_min = params.get("ats_min")
    if ats_min not in (None, ""):
        try:
            queryset = queryset.filter(ats_score__gte=int(ats_min))
        except (TypeError, ValueError):
            pass

    location = (params.get("location") or "").strip()
    if location:
        queryset = queryset.filter(location__icontains=location)

    skills = (params.get("skills") or "").strip()
    if skills:
        queryset = queryset.filter(skills__icontains=skills)

    return queryset.select_related("applicant", "applicant__profile").distinct()


def filter_students(queryset, params):
    """Recruiter-facing candidate search filters (NammaCareer update spec
    sections 8-9). Only ever returns job-seeker profiles that have opted
    into recruiter search (UserSettings.show_in_recruiter_search) - this is
    the one place that privacy rule is enforced for search results, never a
    bypass some other call site could skip.

    Domain/subdomain filters are deliberately not offered here: there is no
    structured domain/subdomain field on a candidate's career preferences
    to filter against (spec section 9: "Do not create filters for fields
    that do not exist").
    """
    queryset = queryset.filter(role=ROLE_JOB_SEEKER, user__settings__show_in_recruiter_search=True)

    name = (params.get("name") or "").strip()
    if name:
        queryset = queryset.filter(
            Q(user__first_name__icontains=name)
            | Q(user__last_name__icontains=name)
            | Q(user__username__icontains=name)
        )

    location = (params.get("location") or "").strip()
    if location:
        queryset = queryset.filter(location__icontains=location)

    skills = (params.get("skills") or "").strip()
    if skills:
        queryset = queryset.filter(Q(skills__icontains=skills) | Q(structured_skills__name__icontains=skills))

    education = (params.get("education") or "").strip()
    if education:
        queryset = queryset.filter(
            Q(education_records__degree__icontains=education) | Q(education_records__level=education)
        )

    college = (params.get("college") or "").strip()
    if college:
        queryset = queryset.filter(education_records__institution__icontains=college)

    min_experience = params.get("min_experience")
    if min_experience not in (None, ""):
        try:
            queryset = queryset.filter(experience_years__gte=int(min_experience))
        except (TypeError, ValueError):
            pass

    experience_level = (params.get("experience_level") or "").strip()
    if experience_level:
        queryset = queryset.filter(career_preference__experience_level=experience_level)

    job_title = (params.get("job_title") or "").strip()
    if job_title:
        queryset = queryset.filter(
            Q(career_preference__preferred_job_title__icontains=job_title) | Q(headline__icontains=job_title)
        )

    industry = (params.get("industry") or "").strip()
    if industry:
        queryset = queryset.filter(career_preference__preferred_industry__icontains=industry)

    employment_type = (params.get("employment_type") or "").strip()
    if employment_type:
        queryset = queryset.filter(career_preference__employment_type=employment_type)

    work_mode = (params.get("work_mode") or "").strip()
    if work_mode:
        queryset = queryset.filter(career_preference__work_mode=work_mode)

    return (
        queryset.select_related("user", "career_preference")
        .prefetch_related("education_records", "structured_skills")
        .distinct()
    )
