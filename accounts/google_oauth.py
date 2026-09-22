"""Minimal Google OAuth2 (Authorization Code) client - no third-party OAuth
library dependency, since the flow needed here is small and well-defined
(spec sections 51-55). Never logs or exposes GOOGLE_CLIENT_SECRET.
"""
import os
from urllib.parse import urlencode

import requests

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

REQUEST_TIMEOUT_SECONDS = 10


class GoogleOAuthError(Exception):
    pass


def is_configured():
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def build_authorization_url(redirect_uri, state):
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_userinfo(code, redirect_uri):
    """Exchanges an authorization code for tokens, then fetches the Google
    profile. Returns a dict with at least 'sub' and 'email'. Raises
    GoogleOAuthError on any failure - never lets a raw requests exception or
    malformed response reach the view.
    """
    try:
        token_response = requests.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise GoogleOAuthError("Could not reach Google. Please try again.") from exc

    if token_response.status_code != 200:
        raise GoogleOAuthError("Google sign-in failed. Please try again.")

    try:
        tokens = token_response.json()
    except ValueError as exc:
        raise GoogleOAuthError("Google sign-in failed. Please try again.") from exc

    access_token = tokens.get("access_token")
    if not access_token:
        raise GoogleOAuthError("Google sign-in failed. Please try again.")

    try:
        userinfo_response = requests.get(
            USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise GoogleOAuthError("Could not reach Google. Please try again.") from exc

    if userinfo_response.status_code != 200:
        raise GoogleOAuthError("Google sign-in failed. Please try again.")

    try:
        userinfo = userinfo_response.json()
    except ValueError as exc:
        raise GoogleOAuthError("Google sign-in failed. Please try again.") from exc

    if not userinfo.get("sub") or not userinfo.get("email"):
        raise GoogleOAuthError("Google did not return the expected profile information.")

    return userinfo
