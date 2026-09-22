from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.constants import THEME_DARK, THEME_LIGHT, THEME_SYSTEM

User = get_user_model()


class ThemeContextProcessorTests(TestCase):
    """Anonymous visitors always render Light Mode - never a saved cookie,
    never the OS/browser preference. Authenticated users keep their existing
    Appearance setting (Light/Dark/System) unchanged."""

    def test_anonymous_user_always_gets_light(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

    def test_anonymous_user_with_dark_cookie_still_gets_light(self):
        self.client.cookies["nc_theme"] = "dark"
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

    def test_anonymous_user_never_gets_declared_system(self):
        """"system" would let the client-side bootstrap script fall through to
        the OS's prefers-color-scheme - anonymous users must never receive it,
        even if an old cookie claims a "system" preference."""
        self.client.cookies["nc_theme"] = "system"
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, 'data-theme="system"')
        self.assertContains(response, 'data-theme="light"')

    def test_incognito_style_request_with_no_cookies_is_light(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

    def test_authenticated_light_preference(self):
        user = User.objects.create_user(username="lightuser", password="pass12345")
        user.settings.theme = THEME_LIGHT
        user.settings.save()
        self.client.login(username="lightuser", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

    def test_authenticated_dark_preference(self):
        user = User.objects.create_user(username="darkuser", password="pass12345")
        user.settings.theme = THEME_DARK
        user.settings.save()
        self.client.login(username="darkuser", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="dark"')

    def test_authenticated_system_preference_declares_system_for_client_resolution(self):
        """Server declares "system"; actual light/dark resolution against the
        OS preference happens client-side (unchanged existing behavior)."""
        user = User.objects.create_user(username="systemuser", password="pass12345")
        user.settings.theme = THEME_SYSTEM
        user.settings.save()
        self.client.login(username="systemuser", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="system"')

    def test_logged_out_dark_user_sees_light_on_next_anonymous_request(self):
        user = User.objects.create_user(username="logoutuser", password="pass12345")
        user.settings.theme = THEME_DARK
        user.settings.save()
        self.client.login(username="logoutuser", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="dark"')

        # A stale theme cookie (as a client-side toggle might once have written)
        # must not leak the authenticated user's Dark preference into the
        # anonymous session after logout.
        self.client.cookies["nc_theme"] = "dark"
        self.client.logout()
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

    def test_anonymous_login_immediately_applies_saved_theme_on_next_response(self):
        user = User.objects.create_user(username="loginuser", password="pass12345")
        user.settings.theme = THEME_DARK
        user.settings.save()

        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

        self.client.login(username="loginuser", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="dark"')

    def test_public_pages_all_render_light_for_anonymous(self):
        for url in [reverse("home"), reverse("jobs:list"), reverse("companies:list"), reverse("accounts:login")]:
            response = self.client.get(url)
            self.assertContains(response, 'data-theme="light"', msg_prefix=url)
