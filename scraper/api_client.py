from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from scraper.config import ScraperConfig


@dataclass
class DiscoveredPosting:
    company: str
    title: str
    url: str
    raw_text: str
    source: str | None = None
    posted_at: date | None = None


@dataclass
class DiscoverResult:
    job_id: str
    status: str
    fit_score: float | None
    recommendation: str | None
    reason: str | None


class ApiClient:
    def __init__(self, config: ScraperConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.api_base_url,
            headers={
                "Authorization": f"Bearer {config.api_token}",
                "User-Agent": config.user_agent,
            },
            timeout=config.request_timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def health(self) -> dict[str, Any]:
        resp = self._client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def discover(self, posting: DiscoveredPosting) -> DiscoverResult:
        if self._config.dry_run:
            return DiscoverResult(
                job_id="<dry-run>",
                status="dry-run",
                fit_score=None,
                recommendation=None,
                reason=f"DRY_RUN=true; would POST {posting.company} / {posting.title}",
            )

        resp = self._client.post(
            "/api/applications/discover",
            json={
                "company": posting.company,
                "title": posting.title,
                "url": posting.url,
                "raw_text": posting.raw_text,
                "source": posting.source,
                "posted_at": posting.posted_at.isoformat() if posting.posted_at else None,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return DiscoverResult(
            job_id=data["job_id"],
            status=data["status"],
            fit_score=data.get("fit_score"),
            recommendation=data.get("recommendation"),
            reason=data.get("reason"),
        )

    def archive_stale(self, max_age_days: int = 7) -> int:
        if self._config.dry_run:
            return 0
        resp = self._client.post(
            "/api/applications/archive-stale",
            params={"max_age_days": max_age_days},
        )
        resp.raise_for_status()
        return resp.json().get("archived", 0)
