from django.db import migrations
from django.utils.text import slugify

from core.constants import JOB_DOMAIN_SEED

# Ordered (domain_slug, subdomain_name, [keywords]) rules used to backfill
# every pre-existing Job's domain/subdomain from its title+skills text (spec
# sections 70-71: "never leave existing jobs without a domain/subdomain").
# First matching rule wins, most-specific rules first; "Software Development"
# is the deliberate general-purpose IT fallback. This is a one-time best-
# effort classification of legacy data - staff can always correct it via the
# job edit form introduced in Phase 6.
BACKFILL_RULES = [
    ("it", "DevOps", ["devops"]),
    ("it", "Cloud Computing", ["cloud"]),
    ("it", "Data Science", ["data analyst", "data scientist", "data science"]),
    (
        "it",
        "Artificial Intelligence / Machine Learning",
        ["machine learning", " ml ", "ai intern", "gen ai", "artificial intelligence", " ai "],
    ),
    ("it", "Mobile Development", ["android developer", "ios developer", "flutter", "react native", "mobile developer"]),
    ("it", "Web Development", ["frontend", "front-end", "react developer", "web developer"]),
    ("it", "UI/UX Design", ["ui/ux", "ux designer", "ui designer", "product designer"]),
    ("it", "QA / Testing", ["qa engineer", "quality analyst", "test engineer", "qa tester", "sdet"]),
    ("it", "Cybersecurity", ["security engineer", "cybersecurity", "pentest"]),
    ("it", "Database", ["dba", "database administrator"]),
    ("it", "Networking", ["network engineer", "networking"]),
    ("it", "Technical Support", ["customer support", "technical support", "help desk"]),
    ("it", "IT Infrastructure", ["system administrator", "infrastructure engineer"]),
    (
        "it",
        "Software Development",
        ["developer", "engineer", "programmer", "django", "python", "java", ".net", "backend", "full stack"],
    ),
    ("non-it", "Human Resources", ["hr executive", "human resources", "hr recruiter"]),
    ("non-it", "Accounting", ["accountant", "accounting"]),
    ("non-it", "Finance", ["finance"]),
    ("non-it", "Sales", ["sales executive", "business development"]),
    ("non-it", "Marketing", ["marketing", "seo executive", "digital marketing"]),
    ("non-it", "Operations", ["operations executive", "operations manager"]),
    ("non-it", "Logistics", ["logistics", "supply chain"]),
    ("non-it", "Administration", ["admin executive", "office administration"]),
    ("non-it", "Mechanical", ["mechanical engineer"]),
    ("non-it", "Civil", ["civil engineer"]),
    ("non-it", "Electrical", ["electrical engineer"]),
    ("non-it", "Electronics", ["electronics engineer"]),
    ("non-it", "Chemical", ["chemical engineer"]),
    ("non-it", "Automobile", ["automobile"]),
    ("non-it", "Manufacturing", ["manufacturing"]),
    ("non-it", "Construction", ["construction", "site engineer"]),
    ("medical-coding", "Medical Coder", ["medical coder", "medical coding"]),
    ("medical-coding", "Medical Billing", ["medical billing"]),
    ("medical-coding", "ICD Coding", ["icd coding", "icd-10"]),
    ("medical-coding", "CPT Coding", ["cpt coding"]),
    ("medical-coding", "HCC Coding", ["hcc coding"]),
    ("medical-coding", "Clinical Documentation", ["clinical documentation"]),
    ("medical-coding", "Medical Claims", ["medical claims", "claims processing"]),
    ("medical-coding", "Healthcare BPO", ["healthcare bpo"]),
    ("medical-coding", "Medical Coding QA", ["medical coding qa"]),
]

# Fallback when no rule matches at all (spec sections 70-71).
FALLBACK_DOMAIN_SLUG = "it"
FALLBACK_SUBDOMAIN_NAME = "Software Development"


def seed_and_backfill(apps, schema_editor):
    JobDomain = apps.get_model("jobs", "JobDomain")
    JobSubdomain = apps.get_model("jobs", "JobSubdomain")
    Job = apps.get_model("jobs", "Job")

    subdomains_by_key = {}
    for order, domain_data in enumerate(JOB_DOMAIN_SEED):
        domain, _ = JobDomain.objects.update_or_create(
            slug=domain_data["slug"],
            defaults={"name": domain_data["name"], "display_order": order, "is_active": True},
        )
        for sub_order, sub_name in enumerate(domain_data["subdomains"]):
            subdomain, _ = JobSubdomain.objects.update_or_create(
                domain=domain,
                name=sub_name,
                # Historical models used inside migrations don't run the real
                # model's save()/slugify logic, so the slug must be set explicitly.
                defaults={"slug": slugify(sub_name), "display_order": sub_order, "is_active": True},
            )
            subdomains_by_key[(domain_data["slug"], sub_name)] = subdomain

    fallback_subdomain = subdomains_by_key[(FALLBACK_DOMAIN_SLUG, FALLBACK_SUBDOMAIN_NAME)]

    for job in Job.objects.all():
        haystack = f"{job.title} {job.skills}".lower()
        target = fallback_subdomain
        for domain_slug, subdomain_name, keywords in BACKFILL_RULES:
            if any(keyword in haystack for keyword in keywords):
                target = subdomains_by_key[(domain_slug, subdomain_name)]
                break
        job.domain_id = target.domain_id
        job.subdomain_id = target.id
        job.save(update_fields=["domain", "subdomain"])


def unseed(apps, schema_editor):
    JobDomain = apps.get_model("jobs", "JobDomain")
    # Job.domain/subdomain are SET_NULL, so this safely clears the backfill too.
    JobDomain.objects.filter(slug__in=[d["slug"] for d in JOB_DOMAIN_SEED]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0003_jobdomain_job_domain_jobsubdomain_job_subdomain_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_and_backfill, unseed),
    ]
