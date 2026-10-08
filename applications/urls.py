from django.urls import path

from applications import views

app_name = "applications"

urlpatterns = [
    path("", views.MyApplicationsListView.as_view(), name="mine"),
    path("interviews/", views.InterviewListView.as_view(), name="interview_list"),
    path("<int:pk>/", views.ApplicationDetailView.as_view(), name="detail"),
    path("<int:pk>/status/", views.UpdateApplicationStatusView.as_view(), name="update_status"),
    path("<int:pk>/resume/<str:mode>/", views.ApplicationResumeView.as_view(), name="resume"),
    path("<int:pk>/notes/add/", views.RecruiterNoteCreateView.as_view(), name="note_add"),
    path("<int:pk>/notes/<int:note_id>/delete/", views.RecruiterNoteDeleteView.as_view(), name="note_delete"),
    path("<int:pk>/interviews/add/", views.InterviewCreateView.as_view(), name="interview_add"),
    path("<int:pk>/interviews/<int:interview_id>/result/", views.InterviewUpdateResultView.as_view(), name="interview_result"),
    path("job/<int:job_id>/apply/", views.ApplyView.as_view(), name="apply"),
    path("job/<int:job_id>/apply/confirm/", views.ApplyConfirmView.as_view(), name="apply_confirm"),
    path("job/<int:job_id>/apply/cancel/", views.ApplyCancelView.as_view(), name="apply_cancel"),
    path("job/<int:job_id>/easy-apply/", views.EasyApplyReviewView.as_view(), name="easy_apply_review"),
    path("job/<int:job_id>/", views.JobApplicationsListView.as_view(), name="for_job"),
]
