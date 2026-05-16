from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ScraperConfig:
    api_base_url: str
    api_token: str
    watchlist_path: Path
    user_agent: str
    request_timeout_seconds: float
    dry_run: bool
    # Politeness controls: enforced globally across all source adapters
    # via scraper.politeness.Politeness.
    inter_request_delay_seconds: float
    max_retries: int
    # Posting freshness: reject postings older than this many days. Set to
    # 0 to disable. Defaults to 30 — most boards re-list active roles
    # frequently enough that anything older is likely stale or already
    # closed.
    max_posting_age_days: int


def load_config() -> ScraperConfig:
    api_base = os.environ.get("API_BASE_URL", "").rstrip("/")
    if not api_base:
        raise RuntimeError("API_BASE_URL is required (e.g. https://api.h4s.live)")
    token = os.environ.get("API_TOKEN", "")
    if not token:
        raise RuntimeError("API_TOKEN is required")

    watchlist_raw = os.environ.get("WATCHLIST_PATH", "watchlist.yaml")
    watchlist_path = Path(watchlist_raw)
    if not watchlist_path.is_absolute():
        watchlist_path = Path(__file__).resolve().parent / watchlist_raw

    return ScraperConfig(
        api_base_url=api_base,
        api_token=token,
        watchlist_path=watchlist_path,
        # Default UA includes a contact URL per HTTP convention so any
        # board operator who notices our traffic can find us.
        user_agent=os.environ.get(
            "USER_AGENT",
            "JobAgentScraper/0.4 (+https://github.com/JustinoChan/Job-Application-Agent)",
        ),
        request_timeout_seconds=float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "20")),
        dry_run=os.environ.get("DRY_RUN", "false").lower() in {"1", "true", "yes"},
        inter_request_delay_seconds=float(os.environ.get("INTER_REQUEST_DELAY_SECONDS", "1.0")),
        max_retries=int(os.environ.get("MAX_RETRIES", "3")),
        max_posting_age_days=int(os.environ.get("MAX_POSTING_AGE_DAYS", "30")),
    )
