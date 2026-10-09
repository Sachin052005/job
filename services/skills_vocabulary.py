"""Curated skill vocabulary used to detect skills inside free-form resume
text (no NER model - deterministic keyword/phrase matching against this
list, reusing core.utils.normalize_skill for the same alias table already
used by CandidateSkill/Profile). Covers the site's own IT / Non-IT /
Medical Coding domains so extraction stays relevant to the jobs actually
posted on TalentPanda."""
import re

from core.utils import SKILL_ALIASES, normalize_skill

IT_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Go", "Rust", "PHP", "Ruby", "Kotlin", "Swift",
    "HTML", "CSS", "SASS", "Bootstrap", "Tailwind CSS",
    "React", "Angular", "Vue.js", "Next.js", "Redux", "jQuery",
    "Node.js", "Django", "Django REST Framework", "Flask", "FastAPI", "Spring Boot", "Express.js", "Laravel",
    "REST API", "GraphQL", "Microservices", "gRPC",
    "MySQL", "PostgreSQL", "MongoDB", "SQLite", "Oracle", "SQL Server", "Redis", "Elasticsearch", "SQL", "NoSQL",
    "AWS", "Azure", "Google Cloud Platform", "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "CI/CD",
    "Git", "GitHub", "GitLab", "Bitbucket", "Linux", "Bash", "Nginx", "Apache",
    "Machine Learning", "Deep Learning", "Artificial Intelligence", "TensorFlow", "PyTorch", "scikit-learn",
    "Pandas", "NumPy", "Data Analysis", "Data Visualization", "Power BI", "Tableau", "Excel",
    "Selenium", "JUnit", "PyTest", "Manual Testing", "Automation Testing", "Postman", "JIRA",
    "Figma", "Adobe XD", "UI/UX Design", "Wireframing", "Prototyping",
    "Networking", "TCP/IP", "DNS", "VPN", "Firewall", "CCNA",
    "Cybersecurity", "Penetration Testing", "SOC", "SIEM",
    "Android", "iOS", "Flutter", "React Native", "Kotlin", "Objective-C",
    "Agile", "Scrum", "Kanban", "DevOps",
]

NON_IT_SKILLS = [
    "AutoCAD", "SolidWorks", "CATIA", "CNC Machining", "Mechanical Design", "Thermodynamics",
    "Civil Engineering", "Structural Analysis", "Surveying", "STAAD Pro", "Revit", "Construction Management",
    "Electrical Wiring", "PLC Programming", "SCADA", "Circuit Design", "Power Systems",
    "Electronics", "Embedded Systems", "PCB Design", "Microcontrollers",
    "Chemical Process Design", "Quality Control", "Six Sigma", "Lean Manufacturing",
    "Automobile Engineering", "Vehicle Diagnostics",
    "Manufacturing Processes", "Production Planning", "Inventory Management", "Supply Chain Management",
    "Logistics Management", "Warehouse Management", "Procurement",
    "Human Resources", "Recruitment", "Payroll", "Employee Relations", "HRIS", "Talent Acquisition",
    "Financial Analysis", "Accounting", "Tally", "SAP", "QuickBooks", "Bookkeeping", "Auditing", "Taxation",
    "GST", "Budgeting", "Financial Modeling",
    "Sales", "Business Development", "Negotiation", "Client Relationship Management", "CRM",
    "Digital Marketing", "SEO", "SEM", "Social Media Marketing", "Content Marketing", "Email Marketing",
    "Market Research", "Brand Management",
    "Operations Management", "Process Improvement",
    "Administration", "Office Management", "Data Entry", "MS Office", "Microsoft Excel", "Microsoft Word",
]

MEDICAL_CODING_SKILLS = [
    "ICD-10", "ICD-10-CM", "ICD-9", "CPT Coding", "HCPCS", "HCC Coding", "DRG Coding",
    "Medical Billing", "Medical Coding", "Medical Claims Processing", "Clinical Documentation Improvement",
    "HIPAA", "EHR", "EMR", "Revenue Cycle Management", "CPC Certification", "CCS Certification",
    "Anatomy and Physiology", "Medical Terminology", "Healthcare Compliance", "Denial Management",
    "Prior Authorization", "Insurance Verification",
]

ALL_SKILLS = sorted(set(IT_SKILLS) | set(NON_IT_SKILLS) | set(MEDICAL_CODING_SKILLS) | set(SKILL_ALIASES.values()))

# Longest phrases first, so "Django REST Framework" matches before the
# shorter "Django" inside the same text region gets a second, redundant hit.
_SKILLS_BY_LENGTH = sorted(ALL_SKILLS, key=len, reverse=True)


def extract_skills(text):
    """Deterministic keyword/phrase scan of `text` against ALL_SKILLS.
    Case-insensitive, word-boundary aware. Returns a deduplicated list of
    canonical skill names (via normalize_skill) in first-seen order."""
    if not text:
        return []
    lower_text = text.lower()
    found = []
    seen = set()
    for skill in _SKILLS_BY_LENGTH:
        key = skill.lower()
        # Word-boundary check without importing re per-call in a hot loop:
        # cheap substring pre-filter, then a precise boundary check only on hits.
        if key not in lower_text:
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])", lower_text):
            canonical = normalize_skill(skill)
            dedup_key = canonical.lower()
            if dedup_key not in seen:
                seen.add(dedup_key)
                found.append(canonical)
    return found
