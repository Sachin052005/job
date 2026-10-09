def theme_context(request):
    """Resolves the single authoritative theme for this request/response.

    The application supports exactly two themes - "light" and "dark" (the
    old "system"/OS-preference option has been removed). The database is
    the single source of truth for authenticated users: their saved
    UserSettings.theme is rendered server-side on every request, so there is
    never a mismatch between what's in the database and what the page shows.

    Anonymous visitors always get "light", full stop - never a leftover
    tp_theme cookie/localStorage value, never anything else. This keeps every
    public page light regardless of browser/OS dark mode or a theme value
    left over from an earlier logged-in Dark session.
    """
    if request.user.is_authenticated:
        settings_obj = getattr(request.user, "settings", None)
        theme = settings_obj.theme if settings_obj else "light"
    else:
        theme = "light"
    # Defensive normalization: anything other than exactly "dark" (a stray
    # legacy "system" value that predates the accounts.0009 data migration,
    # a bad fixture, etc.) renders as "light" - the server must never emit
    # a data-theme value outside the two themes the app actually supports.
    return {"resolved_theme": "dark" if theme == "dark" else "light"}
