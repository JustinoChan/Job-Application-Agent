"""Workday job board API adapter.

Workday exposes a semi-public JSON API on myworkdayjobs.com hosts:
  POST https://{host}/wday/cxs/{tenant}/{site}/jobs  — search/paginate
  GET  https://{host}/wday/cxs/{tenant}/{site}{path}  — job detail

Most Fortune 500 and large tech companies use Workday. Career page URLs
follow the pattern:
  https://{company}.wd{N}.myworkdayjobs.com/{locale}/{site}

Watchlist config:
  - kind: workday
    label: Salesforce
    company_slug: salesforce
    workday_host: salesforce.wd12.myworkdayjobs.com
    workday_site: External
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Iterable

import httpx

from scraper.api_client import DiscoveredPosting
from scraper.politeness import Politeness
from scraper.sources import WatchlistEntry, register
from scraper.sources._html import html_to_text
from scraper.sources._match import title_matches

log = logging.getLogger(__name__)

_MAX_PAGES = 25
_PAGE_SIZE = 20
_POSTED_AGO_RE = re.compile(r"Posted\s+(\d+)\+?\s+Days?\s+Ago", re.IGNORECASE)


def _parse_posted_on(text: str | None) -> date | None:
    if not text:
        return None
    t = text.strip().lower()
    if "today" in t:
        return date.today()
    if "yesterday" in t:
        return date.today() - timedelta(days=1)
    m = _POSTED_AGO_RE.search(text)
    if m:
        return date.today() - timedelta(days=int(m.group(1)))
    return None


@register("workday")
def iter_postings(entry: WatchlistEntry, http: httpx.Client, politeness: Politeness) -> Iterable[DiscoveredPosting]:
    extras = entry.extras or {}
    host = extras.get("workday_host")
    site = extras.get("workday_site", "External")
    tenant = entry.company_slug

    if not host or not tenant:
        log.warning("workday entry %s missing workday_host or company_slug; skipping", entry.display)
        return

    api_base = f"https://{host}/wday/cxs/{tenant}/{site}"
    company_name = entry.label or tenant

    seen_paths: set[str] = set()
    offset = 0
    total: int | None = None

    for _ in range(_MAX_PAGES):
        body = {
            "appliedFacets": {},
            "limit": _PAGE_SIZE,
            "offset": offset,
            "searchText": "",
        }
        try:
            resp = politeness.post(http, f"{api_base}/jobs", json=body)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("workday search failed for %s (offset=%d): %s", entry.display, offset, exc)
            return

        data = resp.json()
        if total is None:
            total = data.get("total", 0)
            log.info("workday:%s total=%d jobs on board", tenant, total)

        postings = data.get("jobPostings", [])
        if not postings:
            break

        for job in postings:
            title = job.get("title") or ""
            if not title_matches(title, entry.match_titles):
                continue

            ext_path = job.get("externalPath") or ""
            if ext_path in seen_paths:
                continue
            seen_paths.add(ext_path)

            location = job.get("locationsText") or ""
            posted_on = _parse_posted_on(job.get("postedOn"))

            raw_text = _compose_text(title, company_name, location, "")
            if ext_path:
                raw_text, posted_on = _fetch_detail(
                    politeness, http, api_base, ext_path,
                    title, company_name, location, posted_on,
                )

            link = f"https://{host}/en-US/{site}{ext_path}" if ext_path else ""

            yield DiscoveredPosting(
                company=company_name,
                title=title,
                url=link,
                raw_text=raw_text,
                source=f"workday:{tenant}",
                posted_at=posted_on,
            )

        offset += _PAGE_SIZE
        if offset >= (total or 0):
            break


def _fetch_detail(
    politeness: Politeness,
    http: httpx.Client,
    api_base: str,
    ext_path: str,
    title: str,
    company: str,
    location: str,
    fallback_date: date | None,
) -> tuple[str, date | None]:
    try:
        resp = politeness.get(http, f"{api_base}{ext_path}")
        if resp.status_code != 200:
            return _compose_text(title, company, location, ""), fallback_date
        detail = resp.json()
        info = detail.get("jobPostingInfo", {})
        desc_html = info.get("jobDescription") or ""
        body_text = html_to_text(desc_html)
        posted_on = fallback_date or _parse_posted_on(info.get("postedOn"))
        return _compose_text(title, company, location, body_text), posted_on
    except Exception:
        log.debug("workday detail fetch failed for %s%s", api_base, ext_path, exc_info=True)
        return _compose_text(title, company, location, ""), fallback_date


def _compose_text(title: str, company: str, location: str, body: str) -> str:
    header = f"{title} | {company}"
    if location:
        header += f"\nLocation: {location}"
    return f"{header}\n\n{body}".strip()
