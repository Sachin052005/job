from django.urls import path

from notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("<int:pk>/open/", views.NotificationReadRedirectView.as_view(), name="open"),
    path("mark-all-read/", views.MarkAllReadView.as_view(), name="mark_all_read"),
    path("<int:pk>/delete/", views.DeleteNotificationView.as_view(), name="delete"),
]
