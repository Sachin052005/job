from django.db.models import Q

from core.constants import JOB_STATUS_PUBLISHED

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

    category = (params.get("category") or "").strip()
    if category:
        queryset = queryset.filter(category__slug=category)

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

    return queryset.select_related("company", "category").distinct()


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

    return queryset.select_related("applicant", "applicant__profile").distinct()
