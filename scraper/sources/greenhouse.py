"""Greenhouse public board API: https://developers.greenhouse.io/job-board.html"""
from __future__ import annotations

import logging
from typing import Iterable

import httpx

from scraper.api_client import DiscoveredPosting
from scraper.sources import WatchlistEntry, register
from scraper.sources._date import parse_iso_date
from scraper.sources._html import html_to_text
from scraper.sources._match import title_matches

log = logging.getLogger(__name__)


@register("greenhouse")
def iter_postings(entry: WatchlistEntry, http: httpx.Client) -> Iterable[DiscoveredPosting]:
    if not entry.company_slug:
        log.warning("greenhouse entry missing company_slug; skipping")
        return
    url = f"https://boards-api.greenhouse.io/v1/boards/{entry.company_slug}/jobs?content=true"
    try:
        resp = http.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("greenhouse fetch failed for %s: %s", entry.company_slug, exc)
        return

    data = resp.json()
    jobs = data.get("jobs", [])
    log.info("greenhouse:%s returned %d jobs", entry.company_slug, len(jobs))

    company_name = entry.label or entry.company_slug
    for job in jobs:
        title = job.get("title") or ""
        if not title_matches(title, entry.match_titles):
            continue
        link = job.get("absolute_url") or ""
        content_html = job.get("content") or ""
        location = (job.get("location") or {}).get("name") or ""
        raw_text = _compose_text(title, company_name, location, html_to_text(content_html))
        # Greenhouse boards only expose updated_at; we use it as the best-available
        # proxy for posted date (a board job rarely updates after first publish).
        posted_at = parse_iso_date(job.get("updated_at"))
        yield DiscoveredPosting(
            company=company_name,
            title=title,
            url=link,
            raw_text=raw_text,
            source=f"greenhouse:{entry.company_slug}",
            posted_at=posted_at,
        )


def _compose_text(title: str, company: str, location: str, body: str) -> str:
    header = f"{title} | {company}"
    if location:
        header += f"\nLocation: {location}"
    return f"{header}\n\n{body}".strip()
