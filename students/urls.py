from django.urls import path

from students import views

app_name = "students"

urlpatterns = [
    path("", views.CandidateSearchView.as_view(), name="search"),
    path("<int:user_id>/", views.CandidateDetailView.as_view(), name="detail"),
]
