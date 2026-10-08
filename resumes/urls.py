from django.urls import path

from resumes import views

app_name = "resumes"

urlpatterns = [
    path("", views.ResumeListView.as_view(), name="list"),
    path("upload/", views.ResumeUploadView.as_view(), name="upload"),
    path("<int:pk>/", views.ResumeDetailView.as_view(), name="detail"),
    path("<int:pk>/scan/", views.ResumeScanView.as_view(), name="scan"),
    path("<int:pk>/job-match/", views.ResumeJobMatchView.as_view(), name="job_match"),
    path("<int:pk>/issues/<int:issue_id>/status/", views.ResumeIssueStatusView.as_view(), name="issue_status"),
    path("<int:pk>/rename/", views.ResumeRenameView.as_view(), name="rename"),
    path("<int:pk>/duplicate/", views.ResumeDuplicateView.as_view(), name="duplicate"),
    path("<int:pk>/set-primary/", views.ResumeSetPrimaryView.as_view(), name="set_primary"),
    path("<int:pk>/delete/", views.ResumeDeleteView.as_view(), name="delete"),
    path("<int:pk>/download/", views.ResumeDownloadView.as_view(), name="download"),
]
