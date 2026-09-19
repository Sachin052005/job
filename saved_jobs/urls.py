from django.urls import path

from saved_jobs import views

app_name = "saved_jobs"

urlpatterns = [
    path("", views.SavedJobsListView.as_view(), name="list"),
    path("<int:job_id>/toggle/", views.ToggleSaveJobView.as_view(), name="toggle"),
]
