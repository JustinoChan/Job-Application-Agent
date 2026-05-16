"""Lever public postings API: https://github.com/lever/postings-api"""
from __future__ import annotations

import logging
from typing import Iterable

import httpx

from scraper.api_client import DiscoveredPosting
from scraper.politeness import Politeness
from scraper.sources import WatchlistEntry, register
from scraper.sources._date import parse_epoch_ms
from scraper.sources._match import title_matches

log = logging.getLogger(__name__)


@register("lever")
def iter_postings(entry: WatchlistEntry, http: httpx.Client, politeness: Politeness) -> Iterable[DiscoveredPosting]:
    if not entry.company_slug:
        log.warning("lever entry missing company_slug; skipping")
        return
    url = f"https://api.lever.co/v0/postings/{entry.company_slug}?mode=json"
    try:
        resp = politeness.get(http, url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("lever fetch failed for %s: %s", entry.company_slug, exc)
        return

    postings = resp.json()
    if not isinstance(postings, list):
        log.warning("lever %s returned non-list payload", entry.company_slug)
        return
    log.info("lever:%s returned %d postings", entry.company_slug, len(postings))

    company_name = entry.label or entry.company_slug
    for post in postings:
        title = post.get("text") or ""
        if not title_matches(title, entry.match_titles):
            continue
        link = post.get("hostedUrl") or post.get("applyUrl") or ""
        cats = post.get("categories") or {}
        location = cats.get("location") or ""
        description = post.get("descriptionPlain") or ""
        lists_text = "\n\n".join(
            f"{item.get('text', '')}\n{item.get('content', '')}"
            for item in (post.get("lists") or [])
        )
        additional = post.get("additionalPlain") or ""
        raw_text = _compose_text(title, company_name, location, description, lists_text, additional)
        posted_at = parse_epoch_ms(post.get("createdAt"))
        yield DiscoveredPosting(
            company=company_name,
            title=title,
            url=link,
            raw_text=raw_text,
            source=f"lever:{entry.company_slug}",
            posted_at=posted_at,
        )


def _compose_text(title: str, company: str, location: str, *body_parts: str) -> str:
    header = f"{title} | {company}"
    if location:
        header += f"\nLocation: {location}"
    body = "\n\n".join(part for part in body_parts if part.strip())
    return f"{header}\n\n{body}".strip()
