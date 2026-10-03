"""Extract text from a PDF CV and detect the skills it mentions."""

import logging
import re
from collections.abc import Iterable
from contextlib import suppress

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .engine import strip_accents

logger = logging.getLogger(__name__)

MAX_CV_TEXT_LENGTH = 20_000

# Common tech skills recognised even if nobody has used them on the platform yet.
SKILL_CATALOG = [
    "Python",
    "Django",
    "Flask",
    "FastAPI",
    "Java",
    "Spring",
    "Kotlin",
    "Scala",
    "JavaScript",
    "TypeScript",
    "React",
    "Angular",
    "Vue.js",
    "Node.js",
    "Next.js",
    "PHP",
    "Laravel",
    "Symfony",
    "Ruby",
    "Rails",
    "Go",
    "Rust",
    "C++",
    "C#",
    ".NET",
    "Swift",
    "Flutter",
    "Dart",
    "HTML",
    "CSS",
    "Bootstrap",
    "Tailwind",
    "SQL",
    "PostgreSQL",
    "MySQL",
    "SQLite",
    "MongoDB",
    "Redis",
    "Elasticsearch",
    "GraphQL",
    "REST",
    "Docker",
    "Kubernetes",
    "Terraform",
    "Ansible",
    "AWS",
    "Azure",
    "GCP",
    "Linux",
    "Git",
    "CI/CD",
    "Jenkins",
    "GitHub Actions",
    "Celery",
    "RabbitMQ",
    "Kafka",
    "Spark",
    "Pandas",
    "NumPy",
    "scikit-learn",
    "TensorFlow",
    "PyTorch",
    "Machine Learning",
    "Data Science",
    "ETL",
    "Power BI",
    "Tableau",
    "Excel",
    "Figma",
    "UX",
    "Agile",
    "Scrum",
    "Jira",
    "TDD",
    "DevOps",
    "Selenium",
    "Cypress",
]


def extract_text(file) -> str:
    """Return the plain text of a PDF file (empty string if unreadable)."""
    try:
        file.seek(0)
        reader = PdfReader(file)
        pages = [page.extract_text() or "" for page in reader.pages[:10]]
    except (PdfReadError, ValueError, OSError, KeyError) as exc:
        logger.info("Could not read CV PDF: %s", exc)
        return ""
    finally:
        with suppress(OSError, ValueError):
            file.seek(0)
    text = " ".join(" ".join(pages).split())
    return text[:MAX_CV_TEXT_LENGTH]


def _skill_pattern(name: str) -> re.Pattern:
    escaped = re.escape(strip_accents(name.lower()))
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9+#])")


def detect_skills(text: str, known_skills: Iterable[str] = ()) -> list[str]:
    """Return the skill names (catalog + known) that appear in the text."""
    haystack = strip_accents((text or "").lower())
    if not haystack:
        return []
    found: dict[str, str] = {}
    for name in [*SKILL_CATALOG, *known_skills]:
        key = name.lower()
        if key in found:
            continue
        if _skill_pattern(name).search(haystack):
            found[key] = name
    return sorted(found.values(), key=str.lower)
