from functools import partial

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.constants import (
    ACCOMPLISHMENT_CATEGORY_CHOICES,
    ACTIVITY_STATUS_ACTIVE_HOURS,
    ACTIVITY_STATUS_AWAY_DAYS,
    ACTIVITY_STATUS_RECENT_DAYS,
    CAREER_EMPLOYMENT_TYPE_CHOICES,
    COMPANY_TYPE_CHOICES,
    EASY_APPLY_REQUIRED_FIELDS,
    EDUCATION_LEVEL_CHOICES,
    EXPERIENCE_LEVEL_CHOICES,
    EMPLOYMENT_TYPE_CHOICES,
    JOB_ALERT_FREQUENCY_CHOICES,
    JOB_ALERT_FREQUENCY_DAILY,
    JOB_SEARCH_STATUS_CHOICES,
    LANGUAGE_PROFICIENCY_CHOICES,
    NOTICE_PERIOD_CHOICES,
    PROFILE_COMPLETENESS_SECTIONS,
    PROFILE_COMPLETION_WEIGHTS,
    PROFILE_VISIBILITY_CHOICES,
    PROFILE_VISIBILITY_RECRUITERS_ONLY,
    RECRUITER_SPECIALIZATION_CHOICES,
    ROLE_CHOICES,
    ROLE_JOB_SEEKER,
    SHIFT_CHOICES,
    SKILL_PROFICIENCY_CHOICES,
    THEME_CHOICES,
    THEME_LIGHT,
    VERIFICATION_STATUS_CHOICES,
    VERIFICATION_UNVERIFIED,
    WORK_MODE_CHOICES,
)
from core.utils import normalize_skill, unique_upload_path
from core.validators import validate_image_file, validate_profile_url, validate_resume_file

# Basic-details fields folded into the "basic_details" completion bucket.
# Deliberately excludes summary/skills/resume, which are scored as their own
# dedicated buckets in PROFILE_COMPLETION_WEIGHTS.
_BASIC_DETAIL_FIELDS = ["headline", "location", "phone", "linkedin_url", "github_url"]


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_JOB_SEEKER)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=120, blank=True)
    headline = models.CharField(max_length=150, blank=True)
    summary = models.TextField(blank=True)
    skills = models.CharField(max_length=500, blank=True, help_text="Comma-separated skills")
    experience_years = models.PositiveSmallIntegerField(default=0)
    photo = models.ImageField(
        upload_to=unique_upload_path("profile_photos"),
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    resume = models.FileField(
        upload_to=unique_upload_path("resumes"),
        blank=True,
        null=True,
        validators=[validate_resume_file],
    )
    linkedin_url = models.URLField(
        max_length=300, blank=True, validators=[partial(validate_profile_url, kind="linkedin")]
    )
    github_url = models.URLField(
        max_length=300, blank=True, validators=[partial(validate_profile_url, kind="github")]
    )
    portfolio_url = models.URLField(max_length=300, blank=True, validators=[validate_profile_url])
    # Kept on the model (not dropped/migrated away) but no longer exposed on the
    # candidate-facing form/template - see spec "remove website field from
    # student profile". Retained for potential employer-side reuse later.
    website_url = models.URLField(max_length=300, blank=True, validators=[validate_profile_url])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Set explicitly via touch_last_updated() rather than auto_now, so trivial
    # saves (e.g. an unrelated field toggle) don't bump this timestamp.
    profile_last_updated = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    def skills_list(self):
        return [s.strip() for s in self.skills.split(",") if s.strip()]

    def effective_skills_list(self):
        """Skills from the flat CSV field plus structured CandidateSkill rows.

        Additive merge only - the CSV field remains the source of truth read
        by Easy Apply; this is for UI/consumers that want the full known
        skill set.
        """
        skills = {normalize_skill(s) for s in self.skills_list()}
        skills.update(self.structured_skills.values_list("name", flat=True))
        return sorted(skills)

    def touch_last_updated(self):
        """Record a meaningful profile edit (not a page view)."""
        now = timezone.now()
        self.profile_last_updated = now
        self.last_activity_at = now
        self.save(update_fields=["profile_last_updated", "last_activity_at"])

    def record_activity(self):
        """Record non-edit meaningful activity (e.g. login)."""
        self.last_activity_at = timezone.now()
        self.save(update_fields=["last_activity_at"])

    def activity_status(self):
        """Privacy-safe, bucketed activity label - never exposes exact timestamps."""
        if not self.last_activity_at:
            return "Not available"
        delta = timezone.now() - self.last_activity_at
        if delta <= timezone.timedelta(hours=ACTIVITY_STATUS_ACTIVE_HOURS):
            return "Active"
        if delta <= timezone.timedelta(days=ACTIVITY_STATUS_RECENT_DAYS):
            return "Recently active"
        if delta <= timezone.timedelta(days=ACTIVITY_STATUS_AWAY_DAYS):
            return "Away"
        return "Not available"

    def completion_percent(self):
        weights = PROFILE_COMPLETION_WEIGHTS
        filled_basic = sum(1 for field in _BASIC_DETAIL_FIELDS if getattr(self, field, ""))
        total = weights["basic_details"] * (filled_basic / len(_BASIC_DETAIL_FIELDS))

        if hasattr(self, "career_preference"):
            total += weights["career_preferences"]
        if self.education_records.exists():
            total += weights["education"]
        if self.summary:
            total += weights["summary"]
        if self.effective_skills_list():
            total += weights["skills"]
        if self.languages.exists():
            total += weights["languages"]
        if self.internships.exists():
            total += weights["internships"]
        if self.projects.exists():
            total += weights["projects"]
        if self.experience_records.exists():
            total += weights["experience"]
        if self.resume:
            total += weights["resume"]

        return int(round(total))

    def missing_sections(self):
        """Labels of recommended profile sections that are still empty."""
        missing = [label for field, label in PROFILE_COMPLETENESS_SECTIONS if not getattr(self, field, "")]
        if not hasattr(self, "career_preference"):
            missing.append("Career preferences")
        if not self.education_records.exists():
            missing.append("Education")
        if not self.languages.exists():
            missing.append("Languages")
        if not self.internships.exists():
            missing.append("Internships")
        if not self.projects.exists():
            missing.append("Projects")
        if not self.experience_records.exists():
            missing.append("Experience")
        return missing

    def is_easy_apply_ready(self):
        """Hard gate for Easy Apply: the fields actually needed to build an application (spec section 2)."""
        if not self.user.first_name or not self.user.email:
            return False
        return all(getattr(self, field, "") for field in EASY_APPLY_REQUIRED_FIELDS)

    def missing_easy_apply_fields(self):
        labels = dict(PROFILE_COMPLETENESS_SECTIONS)
        missing = []
        if not self.user.first_name:
            missing.append("Full name")
        if not self.user.email:
            missing.append("Email")
        missing += [labels.get(field, field) for field in EASY_APPLY_REQUIRED_FIELDS if not getattr(self, field, "")]
        return missing


class CareerPreference(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="career_preference")
    preferred_job_title = models.CharField(max_length=150, blank=True)
    preferred_role = models.CharField(max_length=150, blank=True)
    preferred_industry = models.CharField(max_length=150, blank=True)
    preferred_department = models.CharField(max_length=150, blank=True)
    preferred_location = models.CharField(max_length=120, blank=True)
    work_mode = models.CharField(max_length=20, choices=WORK_MODE_CHOICES, blank=True)
    employment_type = models.CharField(max_length=20, choices=CAREER_EMPLOYMENT_TYPE_CHOICES, blank=True)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVEL_CHOICES, blank=True)
    expected_salary = models.PositiveIntegerField(
        null=True, blank=True, help_text="Annual, in your local currency"
    )
    notice_period = models.CharField(max_length=20, choices=NOTICE_PERIOD_CHOICES, blank=True)
    # blank=True is required here (not just default=) - both fields already
    # have a sensible fallback, so Django's auto-generated ModelForm must
    # treat them as optional. Without it, CareerPreferenceForm silently
    # required these two even though the Application Preferences settings
    # page never displays them, so every save there failed validation with
    # no visible error.
    willing_to_relocate = models.BooleanField(default=False, blank=True)
    preferred_shift = models.CharField(max_length=20, choices=SHIFT_CHOICES, blank=True)
    preferred_company_type = models.CharField(max_length=20, choices=COMPANY_TYPE_CHOICES, blank=True)
    job_search_status = models.CharField(
        max_length=25, choices=JOB_SEARCH_STATUS_CHOICES, default="open_to_opportunities", blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Career preferences for {self.profile.user.get_username()}"


class Education(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="education_records")
    level = models.CharField(max_length=20, choices=EDUCATION_LEVEL_CHOICES, blank=True)
    degree = models.CharField(max_length=150)
    specialization = models.CharField(max_length=150, blank=True)
    institution = models.CharField(max_length=200)
    university = models.CharField(max_length=200, blank=True)
    start_year = models.PositiveSmallIntegerField()
    end_year = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Leave blank if ongoing")
    grade = models.CharField(max_length=50, blank=True, help_text="CGPA or percentage")
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-end_year", "-start_year"]
        indexes = [models.Index(fields=["profile", "order"])]

    def __str__(self):
        return f"{self.degree} - {self.institution}"


class WorkExperience(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="experience_records")
    company = models.CharField(max_length=200)
    designation = models.CharField(max_length=150)
    employment_type = models.CharField(max_length=20, choices=CAREER_EMPLOYMENT_TYPE_CHOICES, blank=True)
    location = models.CharField(max_length=120, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    skills_used = models.CharField(max_length=500, blank=True, help_text="Comma-separated skills")
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-is_current", "-start_date"]
        indexes = [models.Index(fields=["profile", "is_current"])]

    def __str__(self):
        return f"{self.designation} at {self.company}"

    def clean(self):
        if self.is_current:
            self.end_date = None
        elif not self.end_date:
            raise ValidationError({"end_date": "End date is required unless this is your current job."})

    def skills_used_list(self):
        return [s.strip() for s in self.skills_used.split(",") if s.strip()]


class Project(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    technologies = models.CharField(max_length=300, blank=True, help_text="Comma-separated technologies")
    role = models.CharField(max_length=150, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    project_url = models.URLField(max_length=300, blank=True, validators=[validate_profile_url])
    github_url = models.URLField(
        max_length=300, blank=True, validators=[partial(validate_profile_url, kind="github")]
    )
    team_size = models.PositiveSmallIntegerField(null=True, blank=True)
    achievements = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-start_date"]

    def __str__(self):
        return self.title

    def technologies_list(self):
        return [t.strip() for t in self.technologies.split(",") if t.strip()]


class Internship(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="internships")
    company = models.CharField(max_length=200)
    role = models.CharField(max_length=150)
    location = models.CharField(max_length=120, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    skills = models.CharField(max_length=500, blank=True, help_text="Comma-separated skills")
    certificate = models.FileField(
        upload_to=unique_upload_path("internship_certificates"),
        blank=True,
        null=True,
        validators=[validate_resume_file],
    )
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-start_date"]

    def __str__(self):
        return f"{self.role} at {self.company}"

    def skills_list(self):
        return [s.strip() for s in self.skills.split(",") if s.strip()]


class Accomplishment(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="accomplishments")
    category = models.CharField(max_length=20, choices=ACCOMPLISHMENT_CATEGORY_CHOICES, default="certification")
    title = models.CharField(max_length=200)
    issuer = models.CharField(max_length=200, blank=True)
    date = models.DateField(null=True, blank=True)
    url = models.URLField(max_length=300, blank=True, validators=[validate_profile_url])
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-date"]
        indexes = [models.Index(fields=["profile", "category"])]

    def __str__(self):
        return self.title


class Language(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="languages")
    name = models.CharField(max_length=60)
    proficiency = models.CharField(max_length=20, choices=LANGUAGE_PROFICIENCY_CHOICES, default="intermediate")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "name"], name="unique_language_per_profile"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_proficiency_display()})"


class CandidateSkill(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="structured_skills")
    name = models.CharField(max_length=80)
    proficiency = models.CharField(max_length=20, choices=SKILL_PROFICIENCY_CHOICES, blank=True)
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_primary", "name"]
        indexes = [models.Index(fields=["profile", "is_primary"])]
        constraints = [
            models.UniqueConstraint(fields=["profile", "name"], name="unique_skill_per_profile"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = normalize_skill(self.name)
        super().save(*args, **kwargs)


class UserSettings(models.Model):
    """Theme + notification + privacy preferences (spec sections 22, 42, 45)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settings")

    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default=THEME_LIGHT)

    notify_job_alerts = models.BooleanField(default=True)
    notify_application_updates = models.BooleanField(default=True)
    notify_recruiter_updates = models.BooleanField(default=True)
    notify_company_updates = models.BooleanField(default=True)
    notify_interview_reminders = models.BooleanField(default=True)
    notify_system = models.BooleanField(default=True)

    profile_visibility = models.CharField(
        max_length=20, choices=PROFILE_VISIBILITY_CHOICES, default=PROFILE_VISIBILITY_RECRUITERS_ONLY
    )
    recruiters_can_view_profile = models.BooleanField(default=True)
    recruiters_can_download_resume = models.BooleanField(default=True)
    recruiters_can_contact = models.BooleanField(default=True)
    show_in_recruiter_search = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings for {self.user.get_username()}"

    def notifications_enabled_for(self, category):
        from core.constants import NOTIFICATION_CATEGORY_SETTING_FIELD

        field = NOTIFICATION_CATEGORY_SETTING_FIELD.get(category)
        return bool(getattr(self, field, True)) if field else True


class SocialAccount(models.Model):
    """Links one external OAuth identity (Google) to one TalentPanda user (spec section 54)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_accounts")
    provider = models.CharField(max_length=20, default="google")
    provider_user_id = models.CharField(max_length=255, help_text="Stable subject id from the provider (e.g. Google 'sub').")
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["provider", "provider_user_id"], name="unique_social_identity"),
        ]

    def __str__(self):
        return f"{self.provider}:{self.provider_user_id} -> {self.user.get_username()}"


class RecruiterProfile(models.Model):
    """HR/recruiter-facing profile, separate from the candidate-facing Profile (spec section 29)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recruiter_profile")

    job_title = models.CharField(max_length=150, blank=True)
    department = models.CharField(max_length=150, blank=True)
    professional_experience_years = models.PositiveSmallIntegerField(default=0)
    recruitment_experience_years = models.PositiveSmallIntegerField(default=0)
    specialization = models.CharField(max_length=20, choices=RECRUITER_SPECIALIZATION_CHOICES, blank=True)

    roles_hiring_for = models.CharField(max_length=500, blank=True, help_text="Comma-separated roles")
    hiring_domains = models.CharField(max_length=500, blank=True, help_text="Comma-separated domains")
    candidate_experience_pref = models.CharField(max_length=20, choices=EXPERIENCE_LEVEL_CHOICES, blank=True)
    hiring_locations = models.CharField(max_length=500, blank=True, help_text="Comma-separated locations")
    salary_range_min = models.PositiveIntegerField(null=True, blank=True)
    salary_range_max = models.PositiveIntegerField(null=True, blank=True)
    employment_types_hiring = models.CharField(max_length=200, blank=True, help_text="Comma-separated employment types")
    remote_hiring = models.BooleanField(default=False)
    freshers_hiring = models.BooleanField(default=False)
    urgent_hiring = models.BooleanField(default=False)

    company = models.ForeignKey(
        "companies.Company", on_delete=models.SET_NULL, null=True, blank=True, related_name="recruiters"
    )
    designation = models.CharField(max_length=150, blank=True)
    official_company_email = models.EmailField(blank=True)
    employee_id = models.CharField(max_length=60, blank=True)
    recruiter_role = models.CharField(max_length=100, blank=True)

    verification_document = models.FileField(
        upload_to=unique_upload_path("recruiter_verification"),
        blank=True,
        null=True,
        validators=[validate_resume_file],
    )
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS_CHOICES, default=VERIFICATION_UNVERIFIED
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Recruiter profile for {self.user.get_username()}"

    def roles_hiring_for_list(self):
        return [s.strip() for s in self.roles_hiring_for.split(",") if s.strip()]

    def hiring_domains_list(self):
        return [s.strip() for s in self.hiring_domains.split(",") if s.strip()]

    def hiring_locations_list(self):
        return [s.strip() for s in self.hiring_locations.split(",") if s.strip()]


class JobAlert(models.Model):
    """Saved search criteria that trigger a notification when a matching job is published (spec section 38)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_alerts")
    name = models.CharField(max_length=150)
    keywords = models.CharField(max_length=300, blank=True, help_text="Comma-separated keywords")
    domain = models.ForeignKey("jobs.JobDomain", on_delete=models.SET_NULL, null=True, blank=True, related_name="job_alerts")
    location = models.CharField(max_length=150, blank=True)
    experience_max = models.PositiveSmallIntegerField(null=True, blank=True)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, blank=True)
    work_mode = models.CharField(max_length=20, choices=WORK_MODE_CHOICES, blank=True)
    frequency = models.CharField(max_length=10, choices=JOB_ALERT_FREQUENCY_CHOICES, default=JOB_ALERT_FREQUENCY_DAILY)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def keywords_list(self):
        return [s.strip() for s in self.keywords.split(",") if s.strip()]

    def matches(self, job):
        """Deterministic, non-AI match check used when a job is published (spec section 59)."""
        if self.keywords_list():
            haystack = f"{job.title} {job.skills} {job.description}".lower()
            if not any(kw.lower() in haystack for kw in self.keywords_list()):
                return False
        if self.domain_id and job.domain_id != self.domain_id:
            return False
        if self.location and self.location.lower() not in (job.location or "").lower():
            return False
        if self.experience_max is not None and job.experience_min > self.experience_max:
            return False
        if self.salary_min is not None and job.salary_max is not None and job.salary_max < self.salary_min:
            return False
        if self.employment_type and job.employment_type != self.employment_type:
            return False
        if self.work_mode and job.work_mode != self.work_mode:
            return False
        return True
