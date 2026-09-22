from django.urls import path

from adminpanel.views import (
    applications,
    companies,
    dashboard,
    helpcenter,
    job_alerts,
    jobs,
    notifications,
    profiles,
    recruiters,
    reviews,
    saved_jobs,
    search,
    users,
)

app_name = "adminpanel"

urlpatterns = [
    path("", dashboard.DashboardView.as_view(), name="dashboard"),
    path("search/", search.GlobalSearchView.as_view(), name="global_search"),
    # No admin-panel-specific logout route: the sidebar/topbar logout button
    # posts directly to the existing accounts:logout view (see
    # templates/adminpanel/includes/sidebar.html).
    # -- Users ---------------------------------------------------------
    path("users/", users.UserListView.as_view(), name="user_list"),
    path("users/add/", users.UserCreateView.as_view(), name="user_add"),
    path("users/<int:pk>/", users.UserDetailView.as_view(), name="user_detail"),
    path("users/<int:pk>/edit/", users.UserUpdateView.as_view(), name="user_edit"),
    path("users/<int:pk>/delete/", users.UserDeleteView.as_view(), name="user_delete"),
    path("users/<int:pk>/reset-password/", users.UserPasswordResetView.as_view(), name="user_reset_password"),
    # -- Profiles --------------------------------------------------------
    path("profiles/", profiles.ProfileListView.as_view(), name="profile_list"),
    path("profiles/<int:pk>/", profiles.ProfileDetailView.as_view(), name="profile_detail"),
    path("profiles/<int:pk>/edit/", profiles.ProfileUpdateView.as_view(), name="profile_edit"),
    path("profiles/<int:pk>/delete/", profiles.ProfileDeleteView.as_view(), name="profile_delete"),
    # -- Career preferences ----------------------------------------------
    path("career-preferences/", profiles.CareerPreferenceListView.as_view(), name="careerpref_list"),
    path(
        "profiles/<int:profile_pk>/career-preference/add/",
        profiles.CareerPreferenceCreateView.as_view(),
        name="careerpref_add",
    ),
    path("career-preferences/<int:pk>/edit/", profiles.CareerPreferenceUpdateView.as_view(), name="careerpref_edit"),
    path("career-preferences/<int:pk>/delete/", profiles.CareerPreferenceDeleteView.as_view(), name="careerpref_delete"),
    # -- Education ---------------------------------------------------------
    path("education/", profiles.EducationListView.as_view(), name="education_list"),
    path("profiles/<int:profile_pk>/education/add/", profiles.EducationCreateView.as_view(), name="education_add"),
    path("education/<int:pk>/edit/", profiles.EducationUpdateView.as_view(), name="education_edit"),
    path("education/<int:pk>/delete/", profiles.EducationDeleteView.as_view(), name="education_delete"),
    # -- Work experience -----------------------------------------------
    path("experience/", profiles.WorkExperienceListView.as_view(), name="experience_list"),
    path("profiles/<int:profile_pk>/experience/add/", profiles.WorkExperienceCreateView.as_view(), name="experience_add"),
    path("experience/<int:pk>/edit/", profiles.WorkExperienceUpdateView.as_view(), name="experience_edit"),
    path("experience/<int:pk>/delete/", profiles.WorkExperienceDeleteView.as_view(), name="experience_delete"),
    # -- Projects --------------------------------------------------------
    path("projects/", profiles.ProjectListView.as_view(), name="project_list"),
    path("profiles/<int:profile_pk>/projects/add/", profiles.ProjectCreateView.as_view(), name="project_add"),
    path("projects/<int:pk>/edit/", profiles.ProjectUpdateView.as_view(), name="project_edit"),
    path("projects/<int:pk>/delete/", profiles.ProjectDeleteView.as_view(), name="project_delete"),
    # -- Internships -------------------------------------------------------
    path("internships/", profiles.InternshipListView.as_view(), name="internship_list"),
    path("profiles/<int:profile_pk>/internships/add/", profiles.InternshipCreateView.as_view(), name="internship_add"),
    path("internships/<int:pk>/edit/", profiles.InternshipUpdateView.as_view(), name="internship_edit"),
    path("internships/<int:pk>/delete/", profiles.InternshipDeleteView.as_view(), name="internship_delete"),
    # -- Accomplishments -----------------------------------------------
    path("accomplishments/", profiles.AccomplishmentListView.as_view(), name="accomplishment_list"),
    path(
        "profiles/<int:profile_pk>/accomplishments/add/",
        profiles.AccomplishmentCreateView.as_view(),
        name="accomplishment_add",
    ),
    path("accomplishments/<int:pk>/edit/", profiles.AccomplishmentUpdateView.as_view(), name="accomplishment_edit"),
    path("accomplishments/<int:pk>/delete/", profiles.AccomplishmentDeleteView.as_view(), name="accomplishment_delete"),
    # -- Languages -----------------------------------------------------
    path("languages/", profiles.LanguageListView.as_view(), name="language_list"),
    path("profiles/<int:profile_pk>/languages/add/", profiles.LanguageCreateView.as_view(), name="language_add"),
    path("languages/<int:pk>/edit/", profiles.LanguageUpdateView.as_view(), name="language_edit"),
    path("languages/<int:pk>/delete/", profiles.LanguageDeleteView.as_view(), name="language_delete"),
    # -- Candidate skills ------------------------------------------------
    path("skills/", profiles.CandidateSkillListView.as_view(), name="skill_list"),
    path("profiles/<int:profile_pk>/skills/add/", profiles.CandidateSkillCreateView.as_view(), name="skill_add"),
    path("skills/<int:pk>/edit/", profiles.CandidateSkillUpdateView.as_view(), name="skill_edit"),
    path("skills/<int:pk>/delete/", profiles.CandidateSkillDeleteView.as_view(), name="skill_delete"),
    # -- User settings -----------------------------------------------------
    path("user-settings/", profiles.UserSettingsListView.as_view(), name="usersettings_list"),
    path("user-settings/<int:pk>/edit/", profiles.UserSettingsUpdateView.as_view(), name="usersettings_edit"),
    # -- Social accounts -----------------------------------------------
    path("social-accounts/", profiles.SocialAccountListView.as_view(), name="social_list"),
    path("social-accounts/<int:pk>/delete/", profiles.SocialAccountDeleteView.as_view(), name="social_delete"),
    # -- Recruiter profiles ----------------------------------------------
    path("recruiters/", recruiters.RecruiterProfileListView.as_view(), name="recruiter_list"),
    path("recruiters/<int:pk>/", recruiters.RecruiterProfileDetailView.as_view(), name="recruiter_detail"),
    path("recruiters/<int:pk>/edit/", recruiters.RecruiterProfileUpdateView.as_view(), name="recruiter_edit"),
    path("recruiters/<int:pk>/delete/", recruiters.RecruiterProfileDeleteView.as_view(), name="recruiter_delete"),
    # -- Companies -------------------------------------------------------
    path("companies/", companies.CompanyListView.as_view(), name="company_list"),
    path("companies/add/", companies.CompanyCreateView.as_view(), name="company_add"),
    path("companies/<int:pk>/", companies.CompanyDetailView.as_view(), name="company_detail"),
    path("companies/<int:pk>/edit/", companies.CompanyUpdateView.as_view(), name="company_edit"),
    path("companies/<int:pk>/delete/", companies.CompanyDeleteView.as_view(), name="company_delete"),
    # -- Company offices ---------------------------------------------------
    path("offices/", companies.CompanyOfficeListView.as_view(), name="office_list"),
    path("companies/<int:company_pk>/offices/add/", companies.CompanyOfficeCreateView.as_view(), name="office_add"),
    path("offices/<int:pk>/edit/", companies.CompanyOfficeUpdateView.as_view(), name="office_edit"),
    path("offices/<int:pk>/delete/", companies.CompanyOfficeDeleteView.as_view(), name="office_delete"),
    # -- Company salaries --------------------------------------------------
    path("salaries/", companies.CompanySalaryListView.as_view(), name="salary_list"),
    path("companies/<int:company_pk>/salaries/add/", companies.CompanySalaryCreateView.as_view(), name="salary_add"),
    path("salaries/<int:pk>/edit/", companies.CompanySalaryUpdateView.as_view(), name="salary_edit"),
    path("salaries/<int:pk>/delete/", companies.CompanySalaryDeleteView.as_view(), name="salary_delete"),
    # -- Products & services -----------------------------------------------
    path("products/", companies.CompanyProductServiceListView.as_view(), name="product_list"),
    path(
        "companies/<int:company_pk>/products/add/",
        companies.CompanyProductServiceCreateView.as_view(),
        name="product_add",
    ),
    path("products/<int:pk>/edit/", companies.CompanyProductServiceUpdateView.as_view(), name="product_edit"),
    path("products/<int:pk>/delete/", companies.CompanyProductServiceDeleteView.as_view(), name="product_delete"),
    # -- Company followers ---------------------------------------------
    path("followers/", companies.CompanyFollowListView.as_view(), name="follower_list"),
    path("followers/<int:pk>/delete/", companies.CompanyFollowDeleteView.as_view(), name="follower_delete"),
    # -- Jobs --------------------------------------------------------------
    path("jobs/", jobs.JobListView.as_view(), name="job_list"),
    path("jobs/add/", jobs.JobCreateView.as_view(), name="job_add"),
    path("jobs/<int:pk>/", jobs.JobDetailView.as_view(), name="job_detail"),
    path("jobs/<int:pk>/edit/", jobs.JobUpdateView.as_view(), name="job_edit"),
    path("jobs/<int:pk>/delete/", jobs.JobDeleteView.as_view(), name="job_delete"),
    # -- Categories ------------------------------------------------------
    path("categories/", jobs.CategoryListView.as_view(), name="category_list"),
    path("categories/add/", jobs.CategoryCreateView.as_view(), name="category_add"),
    path("categories/<int:pk>/edit/", jobs.CategoryUpdateView.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", jobs.CategoryDeleteView.as_view(), name="category_delete"),
    # -- Applications --------------------------------------------------
    path("applications/", applications.ApplicationListView.as_view(), name="application_list"),
    path("applications/<int:pk>/", applications.ApplicationDetailView.as_view(), name="application_detail"),
    path("applications/<int:pk>/status/", applications.ApplicationStatusUpdateView.as_view(), name="application_status"),
    path("applications/<int:pk>/delete/", applications.ApplicationDeleteView.as_view(), name="application_delete"),
    # -- Reviews -----------------------------------------------------------
    path("reviews/", reviews.CompanyReviewListView.as_view(), name="review_list"),
    path("reviews/<int:pk>/", reviews.CompanyReviewDetailView.as_view(), name="review_detail"),
    path("reviews/<int:pk>/edit/", reviews.CompanyReviewUpdateView.as_view(), name="review_edit"),
    path("reviews/<int:pk>/delete/", reviews.CompanyReviewDeleteView.as_view(), name="review_delete"),
    # -- Notifications -------------------------------------------------
    path("notifications/", notifications.NotificationListView.as_view(), name="notification_list"),
    path("notifications/<int:pk>/", notifications.NotificationDetailView.as_view(), name="notification_detail"),
    path("notifications/<int:pk>/delete/", notifications.NotificationDeleteView.as_view(), name="notification_delete"),
    # -- Help center -----------------------------------------------------
    path("feedback/", helpcenter.FeedbackListView.as_view(), name="feedback_list"),
    path("feedback/<int:pk>/", helpcenter.FeedbackDetailView.as_view(), name="feedback_detail"),
    path("feedback/<int:pk>/delete/", helpcenter.FeedbackDeleteView.as_view(), name="feedback_delete"),
    path("chat-messages/", helpcenter.ChatMessageListView.as_view(), name="chatmessage_list"),
    path("chat-messages/<int:pk>/", helpcenter.ChatMessageDetailView.as_view(), name="chatmessage_detail"),
    path("chat-messages/<int:pk>/delete/", helpcenter.ChatMessageDeleteView.as_view(), name="chatmessage_delete"),
    # -- Saved jobs ------------------------------------------------------
    path("saved-jobs/", saved_jobs.SavedJobListView.as_view(), name="savedjob_list"),
    path("saved-jobs/<int:pk>/delete/", saved_jobs.SavedJobDeleteView.as_view(), name="savedjob_delete"),
    # -- Job alerts ------------------------------------------------------
    path("job-alerts/", job_alerts.JobAlertListView.as_view(), name="jobalert_list"),
    path("job-alerts/<int:pk>/", job_alerts.JobAlertDetailView.as_view(), name="jobalert_detail"),
    path("job-alerts/<int:pk>/edit/", job_alerts.JobAlertUpdateView.as_view(), name="jobalert_edit"),
    path("job-alerts/<int:pk>/delete/", job_alerts.JobAlertDeleteView.as_view(), name="jobalert_delete"),
]
