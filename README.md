# Naukri - Job Portal

A Django-based job portal connecting job seekers with employers: job search and
filtering, applications with status tracking, company profiles, saved jobs, and
role-based dashboards.

## Tech Stack

- **Backend:** Python, Django 5.2
- **Database:** MySQL 8
- **Frontend:** Django Templates, Bootstrap 5, Bootstrap Icons, vanilla JS

## Project Structure

```
Naukri/
├── config/          # Project settings, root URLs
├── core/            # Shared constants, permissions, validators, template tags
├── accounts/        # Registration, login, profile (Profile model, role field)
├── companies/       # Employer company profiles
├── jobs/            # Job postings, categories, search/filter
├── applications/    # Job applications and status workflow
├── saved_jobs/      # Bookmarked jobs for job seekers
├── dashboard/       # Role-based dashboards (seeker / employer)
├── services/        # search_service.py (job search/filter logic)
├── templates/       # Shared base template, navbar/footer, reusable components
├── static/          # CSS/JS
├── scripts/         # seed_database.py, create_admin.py, import_jobs.py
└── media/           # User-uploaded files (resumes, photos, logos)
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
