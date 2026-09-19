"""Idempotent demo data seeder for the Naukri job portal.

Run with:
    python scripts/seed_database.py
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.files.base import ContentFile  # noqa: E402

from applications.models import Application  # noqa: E402
from companies.models import Company  # noqa: E402
from core.constants import JOB_STATUS_PUBLISHED, ROLE_EMPLOYER, ROLE_JOB_SEEKER  # noqa: E402
from jobs.models import Category, Job  # noqa: E402
from saved_jobs.models import SavedJob  # noqa: E402

User = get_user_model()

CATEGORIES = ["Engineering", "Design", "Marketing", "Sales", "Product", "Data & Analytics", "Customer Support", "Finance"]

EMPLOYERS = [
    {"username": "acme_hr", "email": "hr@acme.example", "company": "Acme Technologies", "industry": "Software"},
    {"username": "globex_hr", "email": "hr@globex.example", "company": "Globex Corp", "industry": "Finance"},
    {"username": "initech_hr", "email": "hr@initech.example", "company": "Initech Solutions", "industry": "Consulting"},
]

SEEKERS = [
    {"username": "priya_sharma", "email": "priya@example.com", "first_name": "Priya", "last_name": "Sharma"},
    {"username": "raj_patel", "email": "raj@example.com", "first_name": "Raj", "last_name": "Patel"},
    {"username": "anita_rao", "email": "anita@example.com", "first_name": "Anita", "last_name": "Rao"},
]

JOB_TEMPLATES = [
    {"title": "Backend Developer (Django)", "skills": "Python, Django, MySQL, REST APIs", "employment_type": "full_time", "exp": (2, 5), "salary": (800000, 1500000)},
    {"title": "Frontend Developer (React)", "skills": "JavaScript, React, HTML, CSS", "employment_type": "full_time", "exp": (1, 4), "salary": (600000, 1200000)},
    {"title": "Product Designer", "skills": "Figma, UX Research, Prototyping", "employment_type": "full_time", "exp": (2, 6), "salary": (700000, 1400000)},
    {"title": "Data Analyst", "skills": "SQL, Python, Excel, Tableau", "employment_type": "full_time", "exp": (0, 3), "salary": (500000, 900000)},
    {"title": "DevOps Engineer", "skills": "AWS, Docker, Kubernetes, CI/CD", "employment_type": "full_time", "exp": (3, 7), "salary": (1200000, 2000000)},
    {"title": "Marketing Intern", "skills": "Content Writing, SEO, Social Media", "employment_type": "internship", "exp": (0, 1), "salary": (150000, 250000)},
    {"title": "QA Engineer", "skills": "Manual Testing, Selenium, Test Cases", "employment_type": "full_time", "exp": (1, 4), "salary": (500000, 900000)},
    {"title": "Remote Customer Support", "skills": "Communication, Zendesk, Problem Solving", "employment_type": "remote", "exp": (0, 2), "salary": (300000, 500000)},
]

LOCATIONS = ["Bangalore", "Mumbai", "Pune", "Hyderabad", "Remote", "Delhi NCR"]

FAKE_RESUME = b"%PDF-1.4\n%Fake demo resume content for seed data.\n"


def seed():
    print("Seeding categories...")
    categories = []
    for name in CATEGORIES:
        category, _ = Category.objects.get_or_create(name=name)
        categories.append(category)

    print("Seeding employers and companies...")
    companies = []
    for data in EMPLOYERS:
        user, created = User.objects.get_or_create(
            username=data["username"], defaults={"email": data["email"]}
        )
        if created:
            user.set_password("DemoPass123!")
            user.save()
        user.profile.role = ROLE_EMPLOYER
        user.profile.save()

        company, _ = Company.objects.get_or_create(
            owner=user,
            defaults={
                "name": data["company"],
                "industry": data["industry"],
                "location": LOCATIONS[len(companies) % len(LOCATIONS)],
                "description": f"{data['company']} is a growing company in the {data['industry']} space.",
            },
        )
        companies.append(company)

    print("Seeding job seekers...")
    seekers = []
    for data in SEEKERS:
        user, created = User.objects.get_or_create(
            username=data["username"],
            defaults={"email": data["email"], "first_name": data["first_name"], "last_name": data["last_name"]},
        )
        if created:
            user.set_password("DemoPass123!")
            user.save()
        user.profile.role = ROLE_JOB_SEEKER
        user.profile.location = LOCATIONS[len(seekers) % len(LOCATIONS)]
        user.profile.skills = "Python, Communication, Teamwork"
        user.profile.experience_years = 2
        if not user.profile.resume:
            user.profile.resume.save(f"{user.username}_resume.pdf", ContentFile(FAKE_RESUME), save=False)
        user.profile.save()
        seekers.append(user)

    print("Seeding jobs...")
    jobs = []
    for i, template in enumerate(JOB_TEMPLATES):
        company = companies[i % len(companies)]
        category = categories[i % len(categories)]
        job, _ = Job.objects.get_or_create(
            title=template["title"],
            company=company,
            defaults={
                "employer": company.owner,
                "category": category,
                "location": LOCATIONS[i % len(LOCATIONS)],
                "description": f"We are looking for a {template['title']} to join {company.name}.",
                "responsibilities": "Collaborate with the team, deliver high quality work, and grow your skills.",
                "skills": template["skills"],
                "employment_type": template["employment_type"],
                "experience_min": template["exp"][0],
                "experience_max": template["exp"][1],
                "salary_min": template["salary"][0],
                "salary_max": template["salary"][1],
                "status": JOB_STATUS_PUBLISHED,
            },
        )
        jobs.append(job)

    print("Seeding sample applications and saved jobs...")
    for i, seeker in enumerate(seekers):
        job = jobs[i % len(jobs)]
        if not Application.objects.filter(job=job, applicant=seeker).exists():
            application = Application(
                job=job,
                applicant=seeker,
                cover_letter=f"I'm excited to apply for the {job.title} role.",
            )
            application.resume.save(f"{seeker.username}_application.pdf", ContentFile(FAKE_RESUME), save=False)
            application.save()

        save_target = jobs[(i + 2) % len(jobs)]
        SavedJob.objects.get_or_create(user=seeker, job=save_target)

    print("Done.")
    print(f"Employers: {len(EMPLOYERS)} (password: DemoPass123!)")
    print(f"Job seekers: {len(SEEKERS)} (password: DemoPass123!)")
    print(f"Jobs: {len(jobs)}")


if __name__ == "__main__":
    seed()
