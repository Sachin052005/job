from django.urls import path
from django.views.generic import TemplateView

from helpcenter import views

app_name = "help"

urlpatterns = [
    path("feedback/", views.FeedbackCreateView.as_view(), name="feedback"),
    path("faq/", views.FAQView.as_view(), name="faq"),
    path("chat/", views.ChatView.as_view(), name="chat"),
]
