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
APPLICATION_STATUS_SELECTED = "selected"
APPLICATION_STATUS_REJECTED = "rejected"
APPLICATION_STATUS_HIRED = "hired"

APPLICATION_STATUS_CHOICES = [
    (APPLICATION_STATUS_APPLIED, "Applied"),
    (APPLICATION_STATUS_UNDER_REVIEW, "Under Review"),
    (APPLICATION_STATUS_SHORTLISTED, "Shortlisted"),
    (APPLICATION_STATUS_INTERVIEW, "Interview"),
    (APPLICATION_STATUS_SELECTED, "Selected"),
    (APPLICATION_STATUS_HIRED, "Hired"),
    (APPLICATION_STATUS_REJECTED, "Rejected"),
]

APPLICATION_STATUS_BADGE_CLASS = {
    APPLICATION_STATUS_APPLIED: "secondary",
    APPLICATION_STATUS_UNDER_REVIEW: "info",
    APPLICATION_STATUS_SHORTLISTED: "primary",
    APPLICATION_STATUS_INTERVIEW: "warning",
    APPLICATION_STATUS_SELECTED: "dark",
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

# Profile fields required before a student can use Easy Apply (spec section 2).
# "Full name" and "Email" are checked separately from `request.user` since
# they live on the User model, not Profile - see Profile.is_easy_apply_ready().
EASY_APPLY_REQUIRED_FIELDS = ["phone", "location", "resume", "linkedin_url", "github_url", "skills"]

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

# ---------------------------------------------------------------------------
# Structured candidate profile (career preferences, education, experience, ...)
# ---------------------------------------------------------------------------

WORK_MODE_CHOICES = [
    ("onsite", "On-site"),
    ("hybrid", "Hybrid"),
    ("remote", "Remote"),
]

# Separate from jobs.EMPLOYMENT_TYPE_CHOICES on purpose: this is what a
# candidate is looking for (includes Freelance), not how a Job is posted.
CAREER_EMPLOYMENT_TYPE_CHOICES = [
    ("full_time", "Full-time"),
    ("part_time", "Part-time"),
    ("contract", "Contract"),
    ("internship", "Internship"),
    ("freelance", "Freelance"),
]

EXPERIENCE_LEVEL_CHOICES = [
    ("fresher", "Fresher"),
    ("junior", "0-2 years"),
    ("mid", "2-5 years"),
    ("senior", "5-10 years"),
    ("lead", "10+ years"),
]

NOTICE_PERIOD_CHOICES = [
    ("immediate", "Immediate"),
    ("15_days", "15 Days"),
    ("30_days", "30 Days"),
    ("60_days", "60 Days"),
    ("90_days", "90 Days"),
]

SHIFT_CHOICES = [
    ("day", "Day"),
    ("night", "Night"),
    ("flexible", "Flexible"),
]

COMPANY_TYPE_CHOICES = [
    ("startup", "Startup"),
    ("mnc", "MNC"),
    ("product", "Product-based"),
    ("service", "Service-based"),
    ("any", "Any"),
]

JOB_SEARCH_STATUS_CHOICES = [
    ("actively_looking", "Actively looking"),
    ("open_to_opportunities", "Open to opportunities"),
    ("not_looking", "Not looking"),
]

EDUCATION_LEVEL_CHOICES = [
    ("10th", "10th"),
    ("12th", "12th / Diploma"),
    ("undergraduate", "Undergraduate"),
    ("postgraduate", "Postgraduate"),
    ("doctorate", "Doctorate"),
]

LANGUAGE_PROFICIENCY_CHOICES = [
    ("basic", "Basic"),
    ("intermediate", "Intermediate"),
    ("fluent", "Fluent"),
    ("native", "Native"),
]

SKILL_PROFICIENCY_CHOICES = [
    ("beginner", "Beginner"),
    ("intermediate", "Intermediate"),
    ("advanced", "Advanced"),
    ("expert", "Expert"),
]

ACCOMPLISHMENT_CATEGORY_CHOICES = [
    ("certification", "Certification"),
    ("award", "Award"),
    ("publication", "Publication"),
    ("hackathon", "Hackathon"),
    ("competition", "Competition"),
    ("course", "Course"),
    ("extracurricular", "Extracurricular"),
    ("other", "Other"),
]

# Weighted profile-completion buckets (candidate profile). Must sum to 100.
# Distinct from PROFILE_COMPLETENESS_SECTIONS above, which still drives the
# flat "missing basic fields" labels folded into the basic_details bucket.
PROFILE_COMPLETION_WEIGHTS = {
    "basic_details": 10,
    "career_preferences": 10,
    "education": 15,
    "summary": 10,
    "skills": 15,
    "languages": 5,
    "internships": 5,
    "projects": 10,
    "experience": 10,
    "resume": 10,
}

# Thresholds for Profile.activity_status().
ACTIVITY_STATUS_ACTIVE_HOURS = 24
ACTIVITY_STATUS_RECENT_DAYS = 7
ACTIVITY_STATUS_AWAY_DAYS = 30

# ---------------------------------------------------------------------------
# Job application method (spec section 13) + badges (section 8)
# ---------------------------------------------------------------------------

APPLICATION_METHOD_EASY_APPLY = "easy_apply"
APPLICATION_METHOD_APPLY = "apply"
APPLICATION_METHOD_BOTH = "both"

APPLICATION_METHOD_CHOICES = [
    (APPLICATION_METHOD_EASY_APPLY, "Easy Apply only"),
    (APPLICATION_METHOD_APPLY, "Apply only"),
    (APPLICATION_METHOD_BOTH, "Both Easy Apply and Apply"),
]

JOB_BADGE_CHOICES = [
    ("urgent_hiring", "Urgent Hiring"),
    ("freshers_can_apply", "Freshers Can Apply"),
    ("open_to_12th", "Open to 12th Passouts"),
    ("immediate_joining", "Immediate Joining"),
    ("walkin_interview", "Walk-in Interview"),
    ("remote", "Remote"),
    ("hybrid", "Hybrid"),
    ("featured", "Featured Job"),
]

# ---------------------------------------------------------------------------
# Theme (spec sections 42-43)
# ---------------------------------------------------------------------------

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "system"

THEME_CHOICES = [
    (THEME_LIGHT, "Light"),
    (THEME_DARK, "Dark"),
    (THEME_SYSTEM, "System"),
]

# ---------------------------------------------------------------------------
# Privacy / profile visibility (spec section 45, 61)
# ---------------------------------------------------------------------------

PROFILE_VISIBILITY_PUBLIC = "public"
PROFILE_VISIBILITY_RECRUITERS_ONLY = "recruiters_only"
PROFILE_VISIBILITY_PRIVATE = "private"

PROFILE_VISIBILITY_CHOICES = [
    (PROFILE_VISIBILITY_PUBLIC, "Public"),
    (PROFILE_VISIBILITY_RECRUITERS_ONLY, "Recruiters Only"),
    (PROFILE_VISIBILITY_PRIVATE, "Private"),
]

# ---------------------------------------------------------------------------
# Notifications (spec sections 20-22, 60)
# ---------------------------------------------------------------------------

NOTIFICATION_TYPE_JOB = "job"
NOTIFICATION_TYPE_APPLICATION = "application"
NOTIFICATION_TYPE_RECRUITER = "recruiter"
NOTIFICATION_TYPE_COMPANY = "company"
NOTIFICATION_TYPE_SYSTEM = "system"

NOTIFICATION_TYPE_CHOICES = [
    (NOTIFICATION_TYPE_JOB, "Jobs"),
    (NOTIFICATION_TYPE_APPLICATION, "Applications"),
    (NOTIFICATION_TYPE_RECRUITER, "Recruiters"),
    (NOTIFICATION_TYPE_COMPANY, "Companies"),
    (NOTIFICATION_TYPE_SYSTEM, "System"),
]

# NotificationSettings category -> UserSettings boolean field name.
NOTIFICATION_CATEGORY_SETTING_FIELD = {
    NOTIFICATION_TYPE_JOB: "notify_job_alerts",
    NOTIFICATION_TYPE_APPLICATION: "notify_application_updates",
    NOTIFICATION_TYPE_RECRUITER: "notify_recruiter_updates",
    NOTIFICATION_TYPE_COMPANY: "notify_company_updates",
    NOTIFICATION_TYPE_SYSTEM: "notify_system",
}

# ---------------------------------------------------------------------------
# Job alerts (spec section 38)
# ---------------------------------------------------------------------------

JOB_ALERT_FREQUENCY_INSTANT = "instant"
JOB_ALERT_FREQUENCY_DAILY = "daily"
JOB_ALERT_FREQUENCY_WEEKLY = "weekly"

JOB_ALERT_FREQUENCY_CHOICES = [
    (JOB_ALERT_FREQUENCY_INSTANT, "Instant"),
    (JOB_ALERT_FREQUENCY_DAILY, "Daily"),
    (JOB_ALERT_FREQUENCY_WEEKLY, "Weekly"),
]

# ---------------------------------------------------------------------------
# Recruiter profile (spec section 29)
# ---------------------------------------------------------------------------

RECRUITER_SPECIALIZATION_CHOICES = [
    ("it", "IT"),
    ("software", "Software"),
    ("engineering", "Engineering"),
    ("sales", "Sales"),
    ("marketing", "Marketing"),
    ("finance", "Finance"),
    ("healthcare", "Healthcare"),
    ("manufacturing", "Manufacturing"),
    ("education", "Education"),
    ("bpo", "BPO"),
    ("logistics", "Logistics"),
    ("other", "Other"),
]

VERIFICATION_UNVERIFIED = "unverified"
VERIFICATION_PENDING = "pending"
VERIFICATION_VERIFIED = "verified"

VERIFICATION_STATUS_CHOICES = [
    (VERIFICATION_UNVERIFIED, "Unverified"),
    (VERIFICATION_PENDING, "Pending Review"),
    (VERIFICATION_VERIFIED, "Verified"),
]

# ---------------------------------------------------------------------------
# Feedback (spec section 47)
# ---------------------------------------------------------------------------

FEEDBACK_CATEGORY_CHOICES = [
    ("website", "Website"),
    ("jobs", "Jobs"),
    ("applications", "Applications"),
    ("recruiter", "Recruiter"),
    ("company", "Company"),
    ("account", "Account"),
    ("other", "Other"),
]

# ---------------------------------------------------------------------------
# Student activity / recruiter-action tracking (NammaCareer update spec
# sections 7, 10-13, 32-39, 78-80)
# ---------------------------------------------------------------------------

ACTIVITY_PROFILE_VIEW = "profile_view"
ACTIVITY_SEARCH_APPEARANCE = "search_appearance"
ACTIVITY_RESUME_VIEW = "resume_view"
ACTIVITY_RESUME_DOWNLOAD = "resume_download"
ACTIVITY_SHORTLISTED = "shortlisted"
ACTIVITY_CONTACTED = "contacted"
ACTIVITY_INTERVIEW = "interview"
ACTIVITY_APPLICATION_STATUS = "application_status"
ACTIVITY_PROFILE_UPDATE = "profile_update"

STUDENT_ACTIVITY_EVENT_CHOICES = [
    (ACTIVITY_PROFILE_VIEW, "Profile View"),
    (ACTIVITY_SEARCH_APPEARANCE, "Search Appearance"),
    (ACTIVITY_RESUME_VIEW, "Resume View"),
    (ACTIVITY_RESUME_DOWNLOAD, "Resume Download"),
    (ACTIVITY_SHORTLISTED, "Shortlisted"),
    (ACTIVITY_CONTACTED, "Contacted"),
    (ACTIVITY_INTERVIEW, "Interview"),
    (ACTIVITY_APPLICATION_STATUS, "Application Status Update"),
    (ACTIVITY_PROFILE_UPDATE, "Profile Update"),
]

# Recruiter-initiated event types counted toward the "Recruiter Actions"
# dashboard counter (spec section 35) - excludes PROFILE_UPDATE, which is
# student-initiated and would otherwise inflate the count.
RECRUITER_ACTION_EVENT_TYPES = [
    ACTIVITY_PROFILE_VIEW,
    ACTIVITY_SEARCH_APPEARANCE,
    ACTIVITY_RESUME_VIEW,
    ACTIVITY_RESUME_DOWNLOAD,
    ACTIVITY_SHORTLISTED,
    ACTIVITY_CONTACTED,
    ACTIVITY_INTERVIEW,
    ACTIVITY_APPLICATION_STATUS,
]

PROFILE_VIEW_SOURCE_SEARCH = "candidate_search"
PROFILE_VIEW_SOURCE_APPLICATION = "application"
PROFILE_VIEW_SOURCE_DIRECT = "direct"

PROFILE_VIEW_SOURCE_CHOICES = [
    (PROFILE_VIEW_SOURCE_SEARCH, "Candidate Search"),
    (PROFILE_VIEW_SOURCE_APPLICATION, "Application"),
    (PROFILE_VIEW_SOURCE_DIRECT, "Direct"),
]

# Dedup windows (hours): a repeat of the same event within the window does not
# create a new record/notification (spec sections 7, 10, 12, 78, 80) - defined
# once here so every tracking call site (jobs, activity, notifications) agrees
# on the same policy instead of re-deriving it.
JOB_VIEW_DEDUP_HOURS = 24
PROFILE_VIEW_DEDUP_HOURS = 24
SEARCH_APPEARANCE_DEDUP_HOURS = 24
RESUME_VIEW_DEDUP_HOURS = 24
RESUME_DOWNLOAD_DEDUP_HOURS = 24
NOTIFICATION_DEDUP_HOURS = 24

# ---------------------------------------------------------------------------
# Job domain / subdomain taxonomy (NammaCareer update spec sections 17-21)
# ---------------------------------------------------------------------------

JOB_DOMAIN_IT = "it"
JOB_DOMAIN_NON_IT = "non-it"
JOB_DOMAIN_MEDICAL_CODING = "medical-coding"

# Seed data for the data migration that creates the 3 fixed top-level domains
# and their initial subdomains. Slugs are stable identifiers used elsewhere
# (URL filters, the migration that backfills existing jobs) - do not rename
# without a follow-up migration.
JOB_DOMAIN_SEED = [
    {
        "slug": JOB_DOMAIN_IT,
        "name": "IT",
        "subdomains": [
            "Software Development",
            "Web Development",
            "Mobile Development",
            "Data Science",
            "Artificial Intelligence / Machine Learning",
            "Cybersecurity",
            "Cloud Computing",
            "DevOps",
            "QA / Testing",
            "UI/UX Design",
            "Database",
            "Networking",
            "Technical Support",
            "IT Infrastructure",
        ],
    },
    {
        "slug": JOB_DOMAIN_NON_IT,
        "name": "Non-IT",
        "subdomains": [
            "Mechanical",
            "Civil",
            "Electrical",
            "Electronics",
            "Chemical",
            "Automobile",
            "Manufacturing",
            "Construction",
            "Human Resources",
            "Finance",
            "Accounting",
            "Sales",
            "Marketing",
            "Operations",
            "Logistics",
            "Administration",
        ],
    },
    {
        "slug": JOB_DOMAIN_MEDICAL_CODING,
        "name": "Medical Coding",
        "subdomains": [
            "Medical Coder",
            "Medical Billing",
            "ICD Coding",
            "CPT Coding",
            "HCC Coding",
            "Clinical Documentation",
            "Medical Claims",
            "Healthcare BPO",
            "Medical Coding QA",
        ],
    },
]

# ---------------------------------------------------------------------------
# ATS engine (local/free - no paid APIs). See resumes/services/.
# ---------------------------------------------------------------------------

PARSE_STATUS_PENDING = "pending"
PARSE_STATUS_PARSED = "parsed"
PARSE_STATUS_FAILED = "failed"

PARSE_STATUS_CHOICES = [
    (PARSE_STATUS_PENDING, "Pending"),
    (PARSE_STATUS_PARSED, "Parsed"),
    (PARSE_STATUS_FAILED, "Failed"),
]

# Current resume parser/analyzer version. Bump when parsing or scoring logic
# changes meaningfully, so cached Resume.parsed_* data is known-stale and
# re-parsed rather than silently reused against new logic (spec: ATS
# versioning).
PARSER_VERSION = "1.0"
ANALYZER_VERSION = "1.0"

ATS_STATUS_PENDING = "pending"
ATS_STATUS_PROCESSING = "processing"
ATS_STATUS_COMPLETE = "complete"
ATS_STATUS_FAILED = "failed"

ATS_STATUS_CHOICES = [
    (ATS_STATUS_PENDING, "Pending"),
    (ATS_STATUS_PROCESSING, "Processing"),
    (ATS_STATUS_COMPLETE, "Complete"),
    (ATS_STATUS_FAILED, "Failed"),
]

ISSUE_PRIORITY_HIGH = "high"
ISSUE_PRIORITY_MEDIUM = "medium"
ISSUE_PRIORITY_LOW = "low"

ISSUE_PRIORITY_CHOICES = [
    (ISSUE_PRIORITY_HIGH, "High Priority"),
    (ISSUE_PRIORITY_MEDIUM, "Medium Priority"),
    (ISSUE_PRIORITY_LOW, "Low Priority"),
]

RESUME_SECTION_KEYS = [
    "summary", "skills", "education", "experience", "projects",
    "internships", "certifications", "achievements", "languages",
]

# ---------------------------------------------------------------------------
# Interviews (spec: Interview Management)
# ---------------------------------------------------------------------------

INTERVIEW_TYPE_PHONE = "phone"
INTERVIEW_TYPE_VIDEO = "video"
INTERVIEW_TYPE_ONSITE = "onsite"
INTERVIEW_TYPE_TECHNICAL = "technical"
INTERVIEW_TYPE_HR = "hr"

INTERVIEW_TYPE_CHOICES = [
    (INTERVIEW_TYPE_PHONE, "Phone"),
    (INTERVIEW_TYPE_VIDEO, "Video"),
    (INTERVIEW_TYPE_ONSITE, "Onsite"),
    (INTERVIEW_TYPE_TECHNICAL, "Technical"),
    (INTERVIEW_TYPE_HR, "HR"),
]

INTERVIEW_RESULT_PENDING = "pending"
INTERVIEW_RESULT_PASSED = "passed"
INTERVIEW_RESULT_FAILED = "failed"
INTERVIEW_RESULT_NO_SHOW = "no_show"

INTERVIEW_RESULT_CHOICES = [
    (INTERVIEW_RESULT_PENDING, "Pending"),
    (INTERVIEW_RESULT_PASSED, "Passed"),
    (INTERVIEW_RESULT_FAILED, "Failed"),
    (INTERVIEW_RESULT_NO_SHOW, "No Show"),
]
