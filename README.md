# NammaCareer - Job Portal

A Django-based job portal connecting job seekers with recruiters: job search
and filtering with Easy Apply/Apply enforced per job, application status
tracking with history, company profiles with following, saved jobs, job
alerts, notifications, recruiter profiles, Google sign-in, an Ollama-backed
"Chat for Help" assistant, and a full light/dark/system theme system.

There is no AI/ATS matching, resume scoring, or AI career advice anywhere in
this project - the only AI-adjacent feature is the portal-usage-only
"Chat for Help" (see below).

## Tech Stack

- **Backend:** Python, Django 5.2
- **Database:** MySQL 8
- **Frontend:** Django Templates, Bootstrap 5, Bootstrap Icons, vanilla JS
- **Optional integrations:** Google OAuth2 (login), Ollama (Chat for Help)

## Project Structure

```
Naukri/
├── config/          # Project settings, root URLs
├── core/            # Shared constants, permissions, validators, template tags,
│                     # theme context processor
├── accounts/        # Registration/login, candidate Profile, RecruiterProfile,
│                     # UserSettings (theme/notifications/privacy), SocialAccount,
│                     # JobAlert, Google OAuth views, Settings views
├── companies/        # Company profiles, offices, follow
├── jobs/             # Job postings, categories, screening questions, search/filter
├── applications/     # Applications, status history, screening answers
├── saved_jobs/       # Bookmarked jobs for job seekers
├── notifications/    # Notification model, bell dropdown, notifications page
├── helpcenter/        # Feedback, FAQ, Chat for Help, About
├── dashboard/        # Role-based dashboards (seeker / employer)
├── services/         # search_service.py (job filtering), help_chat_service.py (Ollama)
├── templates/        # Base template, navbar (mega menus + notifications + profile
│                     # drawer), footer, reusable components
├── static/           # CSS (design tokens + dark theme overrides) / JS
├── scripts/          # seed_database.py, create_admin.py, import_jobs.py
└── media/            # User-uploaded files (resumes, photos, logos)
```

## Setup

### 1. Prerequisites

- Python 3.11+
- MySQL 8 running locally, with an empty database created (default name: `job`)

### 2. Virtual environment & dependencies

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Environment variables

Copy `.env.example` to `.env` and fill in your local MySQL credentials:

```powershell
copy .env.example .env
```

```
DEBUG=True
SECRET_KEY=<generate-a-long-random-string>
ALLOWED_HOSTS=127.0.0.1,localhost

DB_NAME=job
DB_USER=root
DB_PASSWORD=<your-mysql-password>
DB_HOST=127.0.0.1
DB_PORT=3306
```

`.env` is gitignored - never commit real credentials.

### 4. Database migrations

```powershell
python manage.py migrate
```

### 5. Create an admin account

Either the interactive way:

```powershell
python manage.py createsuperuser
```

or the scripted, idempotent way (reads `ADMIN_USERNAME` / `ADMIN_EMAIL` /
`ADMIN_PASSWORD` env vars, with sane defaults):

```powershell
python scripts/create_admin.py
```

### 6. Demo data (optional but recommended)

Seeds 3 employers with companies, 3 job seekers, 8 published jobs, and a few
sample applications/saved jobs. Safe to re-run (idempotent via `get_or_create`).

```powershell
python scripts/seed_database.py
```

Demo accounts (password `DemoPass123!` for all): `acme_hr`, `globex_hr`,
`initech_hr` (employers), `priya_sharma`, `raj_patel`, `anita_rao` (job
seekers).

### 7. Run the server

```powershell
python manage.py runserver
```

Visit http://127.0.0.1:8000/

### 8. Run tests

```powershell
python manage.py test
```

## Google OAuth setup (optional)

The "Continue with Google" button on the login page only appears when
`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are both set in `.env`. Without
them, password login/registration work exactly as before - nothing else
depends on Google being configured.

1. Create an OAuth 2.0 Client ID at
   https://console.cloud.google.com/apis/credentials (Application type: Web
   application).
2. **Authorized JavaScript origins:** `http://127.0.0.1:8000` (dev) and your
   production origin.
3. **Authorized redirect URIs:**
   `http://127.0.0.1:8000/accounts/google/callback/` (dev) and
   `https://<your-domain>/accounts/google/callback/` (prod).
4. Copy the client ID/secret into `.env` as `GOOGLE_CLIENT_ID` /
   `GOOGLE_CLIENT_SECRET`. Never commit these.
5. New Google sign-ups land on a role-selection screen
   (`/accounts/google/welcome/`) then continue into profile/company setup.
   If a Google email matches an existing password account, the user is told
   to log in with their password and link Google from
   Settings > Security instead - accounts are never silently merged.

## Ollama setup ("Chat for Help")

`services/help_chat_service.py` calls a local/remote Ollama server's
`/api/chat` endpoint. Configure via `.env`:

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

Install Ollama (https://ollama.com), pull a model (`ollama pull llama3`), and
make sure `ollama serve` is running. If Ollama is unreachable, times out, or
returns something unexpected, `/help/chat/` shows "Chat for Help is
temporarily unavailable." instead of crashing - it never surfaces a raw
error to the user.

## Theme system (light / dark / system)

- Preference is stored per-user in `accounts.UserSettings.theme` for
  authenticated users (`Settings > Appearance`), and in a `nc_theme` cookie/
  `localStorage` entry for anonymous visitors.
- `core/context_processors.py::theme_context` resolves the declared
  preference into every template as `resolved_theme`.
- An inline script at the top of `templates/base.html` sets
  `data-theme="light|dark"` on `<html>` *before* the stylesheet paints (no
  flash of the wrong theme), resolving `"system"` via
  `prefers-color-scheme` and staying live if the OS theme changes mid-session.
- All colors are defined as CSS custom properties in `static/css/style.css`
  (`--nc-*`), with a single `:root[data-theme="dark"]` block overriding the
  token *values* - components don't need separate dark-mode rules as long as
  they reference the tokens, which the existing design system already does
  throughout the site.

## Bulk-importing jobs

To import jobs from an external JSON file into an existing employer's account:

```powershell
python scripts/import_jobs.py path\to\jobs.json --employer-username acme_hr
```

## Key Design Decisions

- **Roles via `Profile`, not a custom `User` model.** `accounts.Profile` has a
  `role` field (`job_seeker` / `employer`) linked one-to-one to Django's
  built-in `User`. This avoids the migration hazards of swapping
  `AUTH_USER_MODEL` after `django.contrib.auth`'s own migrations exist, while
  giving identical functionality. A `Profile` is auto-created for every new
  `User` via a `post_save` signal (`accounts/signals.py`).
- **Ownership + role checks are enforced server-side**, not just hidden in the
  UI. See `core/permissions.py`: `EmployerRequiredMixin` /
  `JobSeekerRequiredMixin` check role; `OwnerRequiredMixin` checks that the
  requesting user owns the object being edited/deleted. Both compose safely
  via cooperative `dispatch()` chaining (a deliberate design choice - stacking
  two `UserPassesTestMixin`-based `test_func()` mixins would silently drop
  one check, since only the first `test_func()` in the MRO wins).
- **Search/filtering is centralized** in `services/search_service.py` rather
  than inlined in the view, since it combines several optional parameters
  (keyword, location, category, employment type, experience, salary).
- **No AI/ATS matching.** An earlier `services/ats_service.py` (resume
  parsing, GitHub/LinkedIn analysis, a weighted job-match score) has been
  removed entirely, along with `Application.match_snapshot`. The only
  remaining AI-adjacent feature is the Ollama-backed Chat for Help, which is
  scoped to portal-usage questions only.
- **`Job.application_method` is enforced server-side**, not just via hidden
  buttons: `ApplyView`/`EasyApplyReviewView` each check
  `job.allows_apply()` / `job.allows_easy_apply()` in `dispatch()` and
  redirect with an error message if that job doesn't accept that method.
- **Notifications always go through `notifications.services.create_notification`**,
  which checks the recipient's `UserSettings` category toggle first - callers
  never create a `Notification` directly, so a disabled category is
  guaranteed to suppress delivery everywhere.
- **`RecruiterProfile` is separate from `Company`** (many recruiters can
  belong to one company via `RecruiterProfile.company`), while `Company.owner`
  remains the original creator/admin - this avoids a risky migration of the
  existing `Company.owner` OneToOneField while still supporting multiple HR
  users per company.

## Production setup notes

- Set `DEBUG=False`, a real `SECRET_KEY`, and a real `ALLOWED_HOSTS` in the
  production `.env`.
- Serve static files via `python manage.py collectstatic` + a real web server
  or CDN (`STATIC_ROOT` is already configured).
- Use a real `EMAIL_BACKEND` (currently the console backend) so password
  reset emails actually deliver.
- Terminate TLS in front of Django - `SESSION_COOKIE_SECURE` /
  `CSRF_COOKIE_SECURE` should be enabled once served over HTTPS.
- Google OAuth's authorized redirect URI must be the `https://` production
  callback URL (see Google OAuth setup above).
