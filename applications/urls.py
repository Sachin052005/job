from django.urls import path

from applications import views

app_name = "applications"

urlpatterns = [
    path("", views.MyApplicationsListView.as_view(), name="mine"),
    path("<int:pk>/", views.ApplicationDetailView.as_view(), name="detail"),
    path("<int:pk>/status/", views.UpdateApplicationStatusView.as_view(), name="update_status"),
    path("job/<int:job_id>/apply/", views.ApplyView.as_view(), name="apply"),
    path("job/<int:job_id>/apply/confirm/", views.ApplyConfirmView.as_view(), name="apply_confirm"),
    path("job/<int:job_id>/apply/cancel/", views.ApplyCancelView.as_view(), name="apply_cancel"),
    path("job/<int:job_id>/easy-apply/", views.EasyApplyReviewView.as_view(), name="easy_apply_review"),
    path("job/<int:job_id>/", views.JobApplicationsListView.as_view(), name="for_job"),
]
