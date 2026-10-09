from django.contrib.auth import views as auth_views
from django.urls import path

from accounts import views
from accounts.google_oauth import is_configured as google_oauth_configured

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path(
        "login/",
        views.TalentPandaLoginView.as_view(
            template_name="registration/login.html",
            extra_context={"google_oauth_configured": google_oauth_configured()},
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("google/login/", views.GoogleLoginView.as_view(), name="google_login"),
    path("google/callback/", views.GoogleCallbackView.as_view(), name="google_callback"),
    path("google/link/", views.GoogleLinkView.as_view(), name="google_link"),
    path("google/welcome/", views.GoogleWelcomeView.as_view(), name="google_welcome"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/edit/", views.ProfileEditView.as_view(), name="profile_edit"),
    path(
        "profile/career-preferences/edit/",
        views.CareerPreferenceEditView.as_view(),
        name="profile_career_preferences_edit",
    ),
    path("profile/education/add/", views.EducationCreateView.as_view(), name="profile_education_add"),
    path("profile/education/<int:pk>/edit/", views.EducationUpdateView.as_view(), name="profile_education_edit"),
    path(
        "profile/education/<int:pk>/delete/",
        views.EducationDeleteView.as_view(),
        name="profile_education_delete",
    ),
    path("profile/experience/add/", views.WorkExperienceCreateView.as_view(), name="profile_experience_add"),
    path(
        "profile/experience/<int:pk>/edit/",
        views.WorkExperienceUpdateView.as_view(),
        name="profile_experience_edit",
    ),
    path(
        "profile/experience/<int:pk>/delete/",
        views.WorkExperienceDeleteView.as_view(),
        name="profile_experience_delete",
    ),
    path("profile/projects/add/", views.ProjectCreateView.as_view(), name="profile_projects_add"),
    path("profile/projects/<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="profile_projects_edit"),
    path("profile/projects/<int:pk>/delete/", views.ProjectDeleteView.as_view(), name="profile_projects_delete"),
    path("profile/internships/add/", views.InternshipCreateView.as_view(), name="profile_internships_add"),
    path(
        "profile/internships/<int:pk>/edit/",
        views.InternshipUpdateView.as_view(),
        name="profile_internships_edit",
    ),
    path(
        "profile/internships/<int:pk>/delete/",
        views.InternshipDeleteView.as_view(),
        name="profile_internships_delete",
    ),
    path(
        "profile/accomplishments/add/",
        views.AccomplishmentCreateView.as_view(),
        name="profile_accomplishments_add",
    ),
    path(
        "profile/accomplishments/<int:pk>/edit/",
        views.AccomplishmentUpdateView.as_view(),
        name="profile_accomplishments_edit",
    ),
    path(
        "profile/accomplishments/<int:pk>/delete/",
        views.AccomplishmentDeleteView.as_view(),
        name="profile_accomplishments_delete",
    ),
    path("profile/languages/add/", views.LanguageCreateView.as_view(), name="profile_languages_add"),
    path("profile/languages/<int:pk>/edit/", views.LanguageUpdateView.as_view(), name="profile_languages_edit"),
    path(
        "profile/languages/<int:pk>/delete/",
        views.LanguageDeleteView.as_view(),
        name="profile_languages_delete",
    ),
    path("profile/skills/add/", views.CandidateSkillCreateView.as_view(), name="profile_skills_add"),
    path("profile/skills/<int:pk>/edit/", views.CandidateSkillUpdateView.as_view(), name="profile_skills_edit"),
    path(
        "profile/skills/<int:pk>/delete/",
        views.CandidateSkillDeleteView.as_view(),
        name="profile_skills_delete",
    ),
    path("performance/", views.StudentPerformanceView.as_view(), name="performance"),
    path("recruiter/performance/", views.RecruiterPerformanceView.as_view(), name="recruiter_performance"),
    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url="/accounts/password/change/done/",
        ),
        name="password_change",
    ),
    path(
        "password/change/done/",
        auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"),
        name="password_change_done",
    ),
    path(
        "password/reset/",
        views.PasswordResetRequestView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            success_url="/accounts/password/reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password/reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url="/accounts/password/reset/complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
