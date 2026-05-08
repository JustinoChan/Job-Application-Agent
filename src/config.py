import re
from pathlib import Path

import yaml

from src.models import (
    ApplicationRules,
    MasterProfile,
    MasterResume,
    Project,
    ProjectBank,
)

BASE_DIR: Path = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
JOBS_DIR = BASE_DIR / "jobs"
JOBS_RAW_DIR = JOBS_DIR / "raw"
OUTPUTS_DIR = BASE_DIR / "outputs"
RESUMES_DIR = OUTPUTS_DIR / "resumes"
COVER_LETTERS_DIR = OUTPUTS_DIR / "cover_letters"
TEMPLATES_DIR = BASE_DIR / "templates"
RESUME_TEMPLATE_PATH = TEMPLATES_DIR / "resume_template.html"
COVER_LETTER_TEMPLATE_PATH = TEMPLATES_DIR / "cover_letter_template.html"

MASTER_PROFILE_PATH = DATA_DIR / "master_profile.yaml"
PROJECT_BANK_PATH = DATA_DIR / "project_bank.yaml"
MASTER_RESUME_PATH = DATA_DIR / "master_resume.yaml"
APPLICATION_RULES_PATH = DATA_DIR / "application_rules.yaml"

TRACKER_PATH = JOBS_DIR / "tracker.csv"


def ensure_directories() -> None:
    for d in [JOBS_RAW_DIR, RESUMES_DIR, COVER_LETTERS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def job_resume_dir(job_id: str) -> Path:
    return RESUMES_DIR / job_id


def next_resume_version(job_id: str) -> int:
    job_dir = job_resume_dir(job_id)
    if not job_dir.exists():
        return 1
    existing = list(job_dir.glob("resume_v*.md"))
    if not existing:
        return 1
    versions = []
    for f in existing:
        match = re.search(r"resume_v(\d+)\.md$", f.name)
        if match:
            versions.append(int(match.group(1)))
    return max(versions) + 1 if versions else 1


def version_paths(job_id: str, version: int) -> dict[str, Path]:
    d = job_resume_dir(job_id)
    v = f"v{version:03d}"
    return {
        "dir": d,
        "md": d / f"resume_{v}.md",
        "meta": d / f"resume_{v}.meta.json",
        "audit": d / f"resume_{v}.audit.json",
        "html": d / f"resume_{v}.html",
        "pdf": d / f"resume_{v}.pdf",
    }


def job_cover_letter_dir(job_id: str) -> Path:
    return COVER_LETTERS_DIR / job_id


def next_cover_letter_version(job_id: str) -> int:
    job_dir = job_cover_letter_dir(job_id)
    if not job_dir.exists():
        return 1
    existing = list(job_dir.glob("cover_letter_v*.md"))
    if not existing:
        return 1
    versions = []
    for f in existing:
        match = re.search(r"cover_letter_v(\d+)\.md$", f.name)
        if match:
            versions.append(int(match.group(1)))
    return max(versions) + 1 if versions else 1


def cover_letter_version_paths(job_id: str, version: int) -> dict[str, Path]:
    d = job_cover_letter_dir(job_id)
    v = f"v{version:03d}"
    return {
        "dir": d,
        "md": d / f"cover_letter_{v}.md",
        "meta": d / f"cover_letter_{v}.meta.json",
        "audit": d / f"cover_letter_{v}.audit.json",
        "html": d / f"cover_letter_{v}.html",
        "pdf": d / f"cover_letter_{v}.pdf",
    }


def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_profile() -> MasterProfile:
    data = load_yaml(MASTER_PROFILE_PATH)
    return MasterProfile(**data)


def load_projects() -> list[Project]:
    data = load_yaml(PROJECT_BANK_PATH)
    bank = ProjectBank(**data)
    return bank.projects


def load_resume_config() -> MasterResume:
    data = load_yaml(MASTER_RESUME_PATH)
    return MasterResume(**data)


def load_rules() -> ApplicationRules:
    data = load_yaml(APPLICATION_RULES_PATH)
    return ApplicationRules(**data)
