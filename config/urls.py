from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from helpcenter.views import AboutView
from jobs.views import HomeView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("about/", AboutView.as_view(), name="about"),
    # Django's built-in admin stays available as a backend/emergency fallback
    # (spec section 27) - the manual admin panel below is additive, not a
    # replacement, and both operate on the same database models.
    path("admin/", admin.site.urls),
    # Manual NammaCareer admin panel: there is deliberately NO separate
    # admin login route - /accounts/login/ is the single login page for the
    # whole site (see accounts.views.NammaCareerLoginView), which redirects
    # staff/superuser accounts here after authenticating.
    path("admin-panel/", include("adminpanel.urls")),
    path("accounts/", include("accounts.urls")),
    path("companies/", include("companies.urls")),
    path("jobs/", include("jobs.urls")),
    path("applications/", include("applications.urls")),
    path("saved-jobs/", include("saved_jobs.urls")),
    path("notifications/", include("notifications.urls")),
    path("job-alerts/", include("accounts.job_alert_urls")),
    path("settings/", include("accounts.settings_urls")),
    path("help/", include("helpcenter.urls")),
    path("dashboard/", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = "core.views_errors.bad_request"
handler403 = "core.views_errors.permission_denied"
handler404 = "core.views_errors.page_not_found"
handler500 = "core.views_errors.server_error"
