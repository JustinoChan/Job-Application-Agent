from __future__ import annotations

from functools import lru_cache

from src import config
from src.models import ApplicationRules, MasterProfile, MasterResume, Project


@lru_cache(maxsize=1)
def get_profile() -> MasterProfile:
    return config.load_profile()


@lru_cache(maxsize=1)
def get_projects() -> tuple[Project, ...]:
    return tuple(config.load_projects())


@lru_cache(maxsize=1)
def get_rules() -> ApplicationRules:
    return config.load_rules()


@lru_cache(maxsize=1)
def get_resume_config() -> MasterResume:
    return config.load_resume_config()


def clear_config_cache() -> None:
    get_profile.cache_clear()
    get_projects.cache_clear()
    get_rules.cache_clear()
    get_resume_config.cache_clear()
