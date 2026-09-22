from django.urls import path

from accounts import views

app_name = "job_alerts"

urlpatterns = [
    path("", views.JobAlertListView.as_view(), name="list"),
    path("create/", views.JobAlertCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.JobAlertUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.JobAlertDeleteView.as_view(), name="delete"),
    path("<int:pk>/toggle/", views.JobAlertToggleView.as_view(), name="toggle"),
]
