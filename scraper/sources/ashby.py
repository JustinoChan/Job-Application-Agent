"""Ashby public job board API: https://developers.ashbyhq.com/reference/jobpostings"""
from __future__ import annotations

import logging
from typing import Iterable

import httpx

from scraper.api_client import DiscoveredPosting
from scraper.sources import WatchlistEntry, register
from scraper.sources._html import html_to_text
from scraper.sources._match import title_matches

log = logging.getLogger(__name__)


@register("ashby")
def iter_postings(entry: WatchlistEntry, http: httpx.Client) -> Iterable[DiscoveredPosting]:
    if not entry.company_slug:
        log.warning("ashby entry missing company_slug; skipping")
        return
    url = f"https://api.ashbyhq.com/posting-api/job-board/{entry.company_slug}?includeCompensation=true"
    try:
        resp = http.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("ashby fetch failed for %s: %s", entry.company_slug, exc)
        return

    data = resp.json()
    jobs = data.get("jobs", [])
    log.info("ashby:%s returned %d jobs", entry.company_slug, len(jobs))

    company_name = entry.label or entry.company_slug
    for job in jobs:
        if job.get("isListed") is False:
            continue
        title = job.get("title") or ""
        if not title_matches(title, entry.match_titles):
            continue
        link = job.get("jobUrl") or job.get("applyUrl") or ""
        location = job.get("locationName") or ""
        body = html_to_text(job.get("descriptionHtml") or job.get("description") or "")
        raw_text = _compose_text(title, company_name, location, body)
        yield DiscoveredPosting(
            company=company_name,
            title=title,
            url=link,
            raw_text=raw_text,
            source=f"ashby:{entry.company_slug}",
        )


def _compose_text(title: str, company: str, location: str, body: str) -> str:
    header = f"{title} | {company}"
    if location:
        header += f"\nLocation: {location}"
    return f"{header}\n\n{body}".strip()
