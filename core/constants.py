ROLE_JOB_SEEKER = "job_seeker"
ROLE_EMPLOYER = "employer"

ROLE_CHOICES = [
    (ROLE_JOB_SEEKER, "Job Seeker"),
    (ROLE_EMPLOYER, "Employer"),
]

EMPLOYMENT_TYPE_CHOICES = [
    ("full_time", "Full Time"),
    ("part_time", "Part Time"),
    ("contract", "Contract"),
    ("internship", "Internship"),
    ("remote", "Remote"),
]

JOB_STATUS_DRAFT = "draft"
JOB_STATUS_PUBLISHED = "published"
JOB_STATUS_CLOSED = "closed"

JOB_STATUS_CHOICES = [
    (JOB_STATUS_DRAFT, "Draft"),
    (JOB_STATUS_PUBLISHED, "Published"),
    (JOB_STATUS_CLOSED, "Closed"),
]

APPLICATION_STATUS_APPLIED = "applied"
APPLICATION_STATUS_UNDER_REVIEW = "under_review"
APPLICATION_STATUS_SHORTLISTED = "shortlisted"
APPLICATION_STATUS_INTERVIEW = "interview"
APPLICATION_STATUS_REJECTED = "rejected"
APPLICATION_STATUS_HIRED = "hired"

APPLICATION_STATUS_CHOICES = [
    (APPLICATION_STATUS_APPLIED, "Applied"),
    (APPLICATION_STATUS_UNDER_REVIEW, "Under Review"),
    (APPLICATION_STATUS_SHORTLISTED, "Shortlisted"),
    (APPLICATION_STATUS_INTERVIEW, "Interview"),
    (APPLICATION_STATUS_REJECTED, "Rejected"),
    (APPLICATION_STATUS_HIRED, "Hired"),
]

APPLICATION_STATUS_BADGE_CLASS = {
    APPLICATION_STATUS_APPLIED: "secondary",
    APPLICATION_STATUS_UNDER_REVIEW: "info",
    APPLICATION_STATUS_SHORTLISTED: "primary",
    APPLICATION_STATUS_INTERVIEW: "warning",
    APPLICATION_STATUS_REJECTED: "danger",
    APPLICATION_STATUS_HIRED: "success",
}

JOB_STATUS_BADGE_CLASS = {
    JOB_STATUS_DRAFT: "secondary",
    JOB_STATUS_PUBLISHED: "success",
    JOB_STATUS_CLOSED: "dark",
}

PAGE_SIZE = 9
APPLICATIONS_PAGE_SIZE = 15

MAX_RESUME_SIZE_MB = 5
MAX_IMAGE_SIZE_MB = 2

APPLIED_VIA_MANUAL = "manual"
APPLIED_VIA_EASY_APPLY = "easy_apply"

APPLIED_VIA_CHOICES = [
    (APPLIED_VIA_MANUAL, "Manual"),
    (APPLIED_VIA_EASY_APPLY, "Easy Apply"),
]

# Fields required before a student can use Easy Apply. Everything else on the
# profile is "recommended" (counted in completeness) but not a hard gate.
EASY_APPLY_REQUIRED_FIELDS = ["resume", "skills"]

# (attribute, label, weight-toward-completion) used by Profile.completion_percent()
# and Profile.missing_sections(). Order controls display order in the UI.
PROFILE_COMPLETENESS_SECTIONS = [
    ("headline", "Professional headline"),
    ("location", "Location"),
    ("phone", "Phone number"),
    ("summary", "Career summary"),
    ("skills", "Skills"),
    ("resume", "Resume"),
    ("linkedin_url", "LinkedIn profile"),
    ("github_url", "GitHub profile"),
]

# Transparent, configurable ATS weighting. Must sum to 100.
ATS_WEIGHTS = {
    "skills": 40,
    "experience": 20,
    "education": 10,
    "keyword": 20,
    "resume_completeness": 10,
}

ATS_MATCH_DISCLAIMER = (
    "This score is an informational match estimate based on the information in your "
    "profile and the job description. It is not a guarantee of hiring."
)
