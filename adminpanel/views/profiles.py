"""Profile + every candidate-side child record (spec sections 9, 17, 46).

Child records (Education, WorkExperience, ...) are always created from a
Profile's detail page (their FK is fixed via FixedParentMixin, not an
editable form field) but can be listed/edited/deleted from their own
top-level nav item too - both entry points share the same views.
"""
from django.urls import reverse

from accounts.forms import (
    AccomplishmentForm,
    CandidateSkillForm,
    CareerPreferenceForm,
    EducationForm,
    InternshipForm,
    LanguageForm,
    ProjectForm,
    WorkExperienceForm,
)
from accounts.models import (
    Accomplishment,
    CandidateSkill,
    CareerPreference,
    Education,
    Internship,
    Language,
    Profile,
    Project,
    SocialAccount,
    UserSettings,
    WorkExperience,
)
from adminpanel.forms import AdminProfileForm, AdminUserSettingsForm, SocialAccountForm
from adminpanel.mixins import (
    AdminCreateView,
    AdminDeleteView,
    AdminDetailView,
    AdminListView,
    AdminUpdateView,
    FilterSpec,
    FixedParentMixin,
)
from core.constants import ROLE_CHOICES


class BackToProfileMixin:
    """After create/edit/delete of a child record, return to the owning
    Profile's detail page rather than the (contextless) top-level list."""

    profile_field = "profile"

    def get_success_url(self):
        profile_id = getattr(self.object, f"{self.profile_field}_id")
        return reverse("adminpanel:profile_detail", kwargs={"pk": profile_id})


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


class ProfileListView(AdminListView):
    model = Profile
    page_title = "Profiles"
    search_fields = ["user__username", "user__email", "location", "headline", "skills"]
    columns = [
        ("User", "user.username"),
        ("Role", "get_role_display"),
        ("Location", "location"),
        ("Experience (yrs)", "experience_years"),
        ("Completion %", "completion_percent"),
        ("Created", "created_at"),
    ]
    filter_specs = [FilterSpec("role", "Role", ROLE_CHOICES)]
    row_view_url_name = "adminpanel:profile_detail"
    row_edit_url_name = "adminpanel:profile_edit"
    row_delete_url_name = "adminpanel:profile_delete"
    ordering = ["-created_at"]
    select_related_fields = ["user"]


class ProfileDetailView(AdminDetailView):
    model = Profile
    template_name = "adminpanel/profiles/detail.html"
    page_title = "Profile"
    edit_url_name = "adminpanel:profile_edit"
    delete_url_name = "adminpanel:profile_delete"
    list_url_name = "adminpanel:profile_list"
    detail_fields = [
        ("User", "user.username"),
        ("Role", "get_role_display"),
        ("Phone", "phone"),
        ("Location", "location"),
        ("Headline", "headline"),
        ("Summary", "summary"),
        ("Skills", "skills"),
        ("Experience (years)", "experience_years"),
        ("Resume", "resume"),
        ("LinkedIn", "linkedin_url"),
        ("GitHub", "github_url"),
        ("Portfolio", "portfolio_url"),
        ("Completion %", "completion_percent"),
        ("Created", "created_at"),
        ("Updated", "updated_at"),
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.object
        pk = profile.pk
        ctx.update(
            {
                "career_preference": getattr(profile, "career_preference", None),
                "user_settings": getattr(profile.user, "settings", None),
                "social_accounts": profile.user.social_accounts.all(),
                "related_table_sections": [
                    (
                        "Education", profile.education_records.all(),
                        [("Degree", "degree"), ("Institution", "institution"), ("Years", "start_year")],
                        reverse("adminpanel:education_add", kwargs={"profile_pk": pk}),
                        "adminpanel:education_edit", "adminpanel:education_delete",
                    ),
                    (
                        "Work Experience", profile.experience_records.all(),
                        [("Designation", "designation"), ("Company", "company"), ("Current", "is_current")],
                        reverse("adminpanel:experience_add", kwargs={"profile_pk": pk}),
                        "adminpanel:experience_edit", "adminpanel:experience_delete",
                    ),
                    (
                        "Projects", profile.projects.all(),
                        [("Title", "title"), ("Technologies", "technologies")],
                        reverse("adminpanel:project_add", kwargs={"profile_pk": pk}),
                        "adminpanel:project_edit", "adminpanel:project_delete",
                    ),
                    (
                        "Internships", profile.internships.all(),
                        [("Role", "role"), ("Company", "company")],
                        reverse("adminpanel:internship_add", kwargs={"profile_pk": pk}),
                        "adminpanel:internship_edit", "adminpanel:internship_delete",
                    ),
                    (
                        "Accomplishments", profile.accomplishments.all(),
                        [("Title", "title"), ("Category", "get_category_display")],
                        reverse("adminpanel:accomplishment_add", kwargs={"profile_pk": pk}),
                        "adminpanel:accomplishment_edit", "adminpanel:accomplishment_delete",
                    ),
                    (
                        "Languages", profile.languages.all(),
                        [("Language", "name"), ("Proficiency", "get_proficiency_display")],
                        reverse("adminpanel:language_add", kwargs={"profile_pk": pk}),
                        "adminpanel:language_edit", "adminpanel:language_delete",
                    ),
                    (
                        "Skills", profile.structured_skills.all(),
                        [("Skill", "name"), ("Proficiency", "get_proficiency_display"), ("Primary", "is_primary")],
                        reverse("adminpanel:skill_add", kwargs={"profile_pk": pk}),
                        "adminpanel:skill_edit", "adminpanel:skill_delete",
                    ),
                ],
            }
        )
        return ctx


class ProfileUpdateView(AdminUpdateView):
    model = Profile
    form_class = AdminProfileForm
    page_title = "Edit Profile"
    list_url_name = "adminpanel:profile_list"
    detail_url_name = "adminpanel:profile_detail"


class ProfileDeleteView(AdminDeleteView):
    model = Profile
    page_title = "Delete Profile"
    list_url_name = "adminpanel:profile_list"


# ---------------------------------------------------------------------------
# Career preference (one per profile)
# ---------------------------------------------------------------------------


class CareerPreferenceListView(AdminListView):
    model = CareerPreference
    page_title = "Career Preferences"
    search_fields = ["profile__user__username", "preferred_job_title", "preferred_role"]
    columns = [
        ("User", "profile.user.username"),
        ("Preferred Title", "preferred_job_title"),
        ("Work Mode", "get_work_mode_display"),
        ("Experience Level", "get_experience_level_display"),
        ("Updated", "updated_at"),
    ]
    row_edit_url_name = "adminpanel:careerpref_edit"
    row_delete_url_name = "adminpanel:careerpref_delete"
    select_related_fields = ["profile__user"]


class CareerPreferenceCreateView(FixedParentMixin, BackToProfileMixin, AdminCreateView):
    model = CareerPreference
    form_class = CareerPreferenceForm
    parent_model = Profile
    parent_field_name = "profile"
    page_title = "Add Career Preference"
    list_url_name = "adminpanel:careerpref_list"


class CareerPreferenceUpdateView(BackToProfileMixin, AdminUpdateView):
    model = CareerPreference
    form_class = CareerPreferenceForm
    page_title = "Edit Career Preference"
    list_url_name = "adminpanel:careerpref_list"


class CareerPreferenceDeleteView(AdminDeleteView):
    model = CareerPreference
    page_title = "Delete Career Preference"
    list_url_name = "adminpanel:careerpref_list"


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------


class EducationListView(AdminListView):
    model = Education
    page_title = "Education"
    search_fields = ["profile__user__username", "degree", "institution"]
    columns = [
        ("User", "profile.user.username"),
        ("Degree", "degree"),
        ("Institution", "institution"),
        ("Start", "start_year"),
        ("End", "end_year"),
    ]
    row_edit_url_name = "adminpanel:education_edit"
    row_delete_url_name = "adminpanel:education_delete"
    select_related_fields = ["profile__user"]


class EducationCreateView(FixedParentMixin, BackToProfileMixin, AdminCreateView):
    model = Education
    form_class = EducationForm
    parent_model = Profile
    page_title = "Add Education"
    list_url_name = "adminpanel:education_list"


class EducationUpdateView(BackToProfileMixin, AdminUpdateView):
    model = Education
    form_class = EducationForm
    page_title = "Edit Education"
    list_url_name = "adminpanel:education_list"


class EducationDeleteView(AdminDeleteView):
    model = Education
    page_title = "Delete Education"
    list_url_name = "adminpanel:education_list"


# ---------------------------------------------------------------------------
# Work experience
# ---------------------------------------------------------------------------


class WorkExperienceListView(AdminListView):
    model = WorkExperience
    page_title = "Work Experience"
    search_fields = ["profile__user__username", "company", "designation"]
    columns = [
        ("User", "profile.user.username"),
        ("Designation", "designation"),
        ("Company", "company"),
        ("Current", "is_current"),
        ("Start", "start_date"),
    ]
    row_edit_url_name = "adminpanel:experience_edit"
    row_delete_url_name = "adminpanel:experience_delete"
    select_related_fields = ["profile__user"]


class WorkExperienceCreateView(FixedParentMixin, BackToProfileMixin, AdminCreateView):
    model = WorkExperience
    form_class = WorkExperienceForm
    parent_model = Profile
    page_title = "Add Work Experience"
    list_url_name = "adminpanel:experience_list"


class WorkExperienceUpdateView(BackToProfileMixin, AdminUpdateView):
    model = WorkExperience
    form_class = WorkExperienceForm
    page_title = "Edit Work Experience"
    list_url_name = "adminpanel:experience_list"


class WorkExperienceDeleteView(AdminDeleteView):
    model = WorkExperience
    page_title = "Delete Work Experience"
    list_url_name = "adminpanel:experience_list"


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectListView(AdminListView):
    model = Project
    page_title = "Projects"
    search_fields = ["profile__user__username", "title", "technologies"]
    columns = [("User", "profile.user.username"), ("Title", "title"), ("Technologies", "technologies")]
    row_edit_url_name = "adminpanel:project_edit"
    row_delete_url_name = "adminpanel:project_delete"
    select_related_fields = ["profile__user"]


class ProjectCreateView(FixedParentMixin, BackToProfileMixin, AdminCreateView):
    model = Project
    form_class = ProjectForm
    parent_model = Profile
    page_title = "Add Project"
    list_url_name = "adminpanel:project_list"


class ProjectUpdateView(BackToProfileMixin, AdminUpdateView):
    model = Project
    form_class = ProjectForm
    page_title = "Edit Project"
    list_url_name = "adminpanel:project_list"


class ProjectDeleteView(AdminDeleteView):
    model = Project
    page_title = "Delete Project"
    list_url_name = "adminpanel:project_list"


# ---------------------------------------------------------------------------
# Internships
# ---------------------------------------------------------------------------


class InternshipListView(AdminListView):
    model = Internship
    page_title = "Internships"
    search_fields = ["profile__user__username", "company", "role"]
    columns = [("User", "profile.user.username"), ("Role", "role"), ("Company", "company")]
    row_edit_url_name = "adminpanel:internship_edit"
    row_delete_url_name = "adminpanel:internship_delete"
    select_related_fields = ["profile__user"]


class InternshipCreateView(FixedParentMixin, BackToProfileMixin, AdminCreateView):
    model = Internship
    form_class = InternshipForm
    parent_model = Profile
    page_title = "Add Internship"
    list_url_name = "adminpanel:internship_list"


class InternshipUpdateView(BackToProfileMixin, AdminUpdateView):
    model = Internship
    form_class = InternshipForm
    page_title = "Edit Internship"
    list_url_name = "adminpanel:internship_list"


class InternshipDeleteView(AdminDeleteView):
    model = Internship
    page_title = "Delete Internship"
    list_url_name = "adminpanel:internship_list"


# ---------------------------------------------------------------------------
# Accomplishments
# ---------------------------------------------------------------------------


class AccomplishmentListView(AdminListView):
    model = Accomplishment
    page_title = "Accomplishments"
    search_fields = ["profile__user__username", "title", "issuer"]
    columns = [("User", "profile.user.username"), ("Title", "title"), ("Category", "get_category_display")]
    row_edit_url_name = "adminpanel:accomplishment_edit"
    row_delete_url_name = "adminpanel:accomplishment_delete"
    select_related_fields = ["profile__user"]


class AccomplishmentCreateView(FixedParentMixin, BackToProfileMixin, AdminCreateView):
    model = Accomplishment
    form_class = AccomplishmentForm
    parent_model = Profile
    page_title = "Add Accomplishment"
    list_url_name = "adminpanel:accomplishment_list"


class AccomplishmentUpdateView(BackToProfileMixin, AdminUpdateView):
    model = Accomplishment
    form_class = AccomplishmentForm
    page_title = "Edit Accomplishment"
    list_url_name = "adminpanel:accomplishment_list"


class AccomplishmentDeleteView(AdminDeleteView):
    model = Accomplishment
    page_title = "Delete Accomplishment"
    list_url_name = "adminpanel:accomplishment_list"


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------


class LanguageListView(AdminListView):
    model = Language
    page_title = "Languages"
    search_fields = ["profile__user__username", "name"]
    columns = [("User", "profile.user.username"), ("Language", "name"), ("Proficiency", "get_proficiency_display")]
    row_edit_url_name = "adminpanel:language_edit"
    row_delete_url_name = "adminpanel:language_delete"
    select_related_fields = ["profile__user"]


class LanguageCreateView(FixedParentMixin, BackToProfileMixin, AdminCreateView):
    model = Language
    form_class = LanguageForm
    parent_model = Profile
    page_title = "Add Language"
    list_url_name = "adminpanel:language_list"


class LanguageUpdateView(BackToProfileMixin, AdminUpdateView):
    model = Language
    form_class = LanguageForm
    page_title = "Edit Language"
    list_url_name = "adminpanel:language_list"


class LanguageDeleteView(AdminDeleteView):
    model = Language
    page_title = "Delete Language"
    list_url_name = "adminpanel:language_list"


# ---------------------------------------------------------------------------
# Candidate skills
# ---------------------------------------------------------------------------


class CandidateSkillListView(AdminListView):
    model = CandidateSkill
    page_title = "Candidate Skills"
    search_fields = ["profile__user__username", "name"]
    columns = [
        ("User", "profile.user.username"),
        ("Skill", "name"),
        ("Proficiency", "get_proficiency_display"),
        ("Primary", "is_primary"),
    ]
    row_edit_url_name = "adminpanel:skill_edit"
    row_delete_url_name = "adminpanel:skill_delete"
    select_related_fields = ["profile__user"]


class CandidateSkillCreateView(FixedParentMixin, BackToProfileMixin, AdminCreateView):
    model = CandidateSkill
    form_class = CandidateSkillForm
    parent_model = Profile
    page_title = "Add Skill"
    list_url_name = "adminpanel:skill_list"


class CandidateSkillUpdateView(BackToProfileMixin, AdminUpdateView):
    model = CandidateSkill
    form_class = CandidateSkillForm
    page_title = "Edit Skill"
    list_url_name = "adminpanel:skill_list"


class CandidateSkillDeleteView(AdminDeleteView):
    model = CandidateSkill
    page_title = "Delete Skill"
    list_url_name = "adminpanel:skill_list"


# ---------------------------------------------------------------------------
# User settings (one per user; edit only - always exists via signal)
# ---------------------------------------------------------------------------


class UserSettingsListView(AdminListView):
    model = UserSettings
    page_title = "User Settings"
    search_fields = ["user__username", "user__email"]
    columns = [("User", "user.username"), ("Theme", "get_theme_display"), ("Profile Visibility", "get_profile_visibility_display")]
    row_edit_url_name = "adminpanel:usersettings_edit"
    select_related_fields = ["user"]


class UserSettingsUpdateView(AdminUpdateView):
    model = UserSettings
    form_class = AdminUserSettingsForm
    page_title = "Edit User Settings"
    list_url_name = "adminpanel:usersettings_list"


# ---------------------------------------------------------------------------
# Social accounts (linked Google identities)
# ---------------------------------------------------------------------------


class SocialAccountListView(AdminListView):
    model = SocialAccount
    page_title = "Social Accounts"
    search_fields = ["user__username", "provider", "email"]
    columns = [("User", "user.username"), ("Provider", "provider"), ("Email", "email"), ("Linked", "created_at")]
    row_delete_url_name = "adminpanel:social_delete"
    select_related_fields = ["user"]


class SocialAccountDeleteView(AdminDeleteView):
    model = SocialAccount
    page_title = "Unlink Social Account"
    list_url_name = "adminpanel:social_list"
