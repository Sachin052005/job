def theme_context(request):
    """Resolves the "declared" theme for this request - the actual light/dark
    render still happens client-side for 'system' via prefers-color-scheme,
    but this gives the inline bootstrap script and templates a starting value
    without waiting on JS (spec section 42-43).

    Anonymous visitors always get "light", full stop - never a leftover
    nc_theme cookie, never "system" (which would let the inline bootstrap
    script fall through to the OS's prefers-color-scheme). This is what keeps
    every public page light regardless of browser/OS dark mode or a theme
    cookie set during an earlier logged-in Dark session. Authenticated users
    are unaffected: their saved Appearance preference (Light/Dark/System)
    from UserSettings.theme is used exactly as before.
    """
    if request.user.is_authenticated:
        theme = getattr(request.user, "settings", None)
        theme = theme.theme if theme else "system"
    else:
        theme = "light"
    return {"resolved_theme": theme}
