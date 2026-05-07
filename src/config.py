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
AUDITS_DIR = OUTPUTS_DIR / "audits"
TEMPLATES_DIR = BASE_DIR / "templates"

MASTER_PROFILE_PATH = DATA_DIR / "master_profile.yaml"
PROJECT_BANK_PATH = DATA_DIR / "project_bank.yaml"
MASTER_RESUME_PATH = DATA_DIR / "master_resume.yaml"
APPLICATION_RULES_PATH = DATA_DIR / "application_rules.yaml"

TRACKER_PATH = JOBS_DIR / "tracker.csv"


def ensure_directories() -> None:
    for d in [JOBS_RAW_DIR, RESUMES_DIR, COVER_LETTERS_DIR, AUDITS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


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
