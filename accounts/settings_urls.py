from django.urls import path
from django.views.generic import RedirectView

from accounts import views

app_name = "settings"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="settings:account", permanent=False), name="home"),
    path("account/", views.SettingsAccountView.as_view(), name="account"),
    path("security/password/", views.SettingsSecurityPasswordView.as_view(), name="security_password"),
    path("appearance/", views.SettingsAppearanceView.as_view(), name="appearance"),
    path("notifications/", views.SettingsNotificationsView.as_view(), name="notifications"),
    path("privacy/", views.SettingsPrivacyView.as_view(), name="privacy"),
    path(
        "application-preferences/",
        views.SettingsApplicationPreferencesView.as_view(),
        name="application_preferences",
    ),
]
