from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from core.constants import ROLE_EMPLOYER, ROLE_JOB_SEEKER


def _role(user):
    profile = getattr(user, "profile", None)
    return profile.role if profile is not None else None


def _redirect_to_login_with_next(request):
    # django.contrib.auth.views.redirect_to_login safely builds
    # LOGIN_URL?next=<path> (it's what LoginRequiredMixin itself uses) -
    # plain redirect("accounts:login") drops the return path, which is what
    # was silently dropping `next` for JobSeekerRequiredMixin/
    # EmployerRequiredMixin-gated pages (e.g. Settings > Application
    # Preferences) while plain LoginRequiredMixin-gated pages preserved it.
    return redirect_to_login(request.get_full_path())


def employer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _redirect_to_login_with_next(request)
        if _role(request.user) != ROLE_EMPLOYER:
            raise PermissionDenied("Only employers can access this page.")
        return view_func(request, *args, **kwargs)

    return wrapper


def job_seeker_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _redirect_to_login_with_next(request)
        if _role(request.user) != ROLE_JOB_SEEKER:
            raise PermissionDenied("Only job seekers can access this page.")
        return view_func(request, *args, **kwargs)

    return wrapper


class EmployerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return _role(self.request.user) == ROLE_EMPLOYER

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return _redirect_to_login_with_next(self.request)
        raise PermissionDenied("Only employers can access this page.")


class JobSeekerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return _role(self.request.user) == ROLE_JOB_SEEKER

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return _redirect_to_login_with_next(self.request)
        raise PermissionDenied("Only job seekers can access this page.")


def admin_required(view_func):
    """Gate a function-based view on is_staff or is_superuser (manual admin panel).

    Mirrors employer_required/job_seeker_required above - kept here rather
    than in adminpanel/ so all role/permission gates live in one place.
    There is no separate admin login route: an unauthenticated request is
    sent to the same settings.LOGIN_URL ("accounts:login") everyone else uses.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _redirect_to_login_with_next(request)
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Only staff accounts can access the NammaCareer admin panel.")
        return view_func(request, *args, **kwargs)

    return wrapper


class OwnerRequiredMixin:
    """Requires self.get_object() to have an `owner_field` attribute equal to request.user.

    Implemented as a dispatch() override (not test_func()) so it composes correctly
    with EmployerRequiredMixin/JobSeekerRequiredMixin: those also subclass
    UserPassesTestMixin, and a class can only have one effective test_func() in its
    MRO - stacking two test_func-based mixins would silently drop one check.
    """

    owner_field = "employer"

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        owner = obj
        for part in self.owner_field.split("__"):
            owner = getattr(owner, part, None)
        if owner != request.user:
            raise PermissionDenied("You do not have permission to modify this resource.")
        return super().dispatch(request, *args, **kwargs)
