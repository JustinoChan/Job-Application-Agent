"""HN 'Ask HN: Who is hiring?' adapter via the Algolia API.

Finds the latest monthly thread, then yields one DiscoveredPosting per
top-level comment whose body matches any of `match_keywords`. Company/title
are best-effort extracted from the first line, which by convention is
`Company | Title | Location | ...`.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

import httpx

from scraper.api_client import DiscoveredPosting
from scraper.sources import WatchlistEntry, register
from scraper.sources._date import parse_iso_date
from scraper.sources._html import html_to_text
from scraper.sources._match import keyword_matches

log = logging.getLogger(__name__)

_SEARCH_BY_DATE_URL = "https://hn.algolia.com/api/v1/search_by_date"
_ITEM_URL_TPL = "https://hn.algolia.com/api/v1/items/{id}"
_URL_RE = re.compile(r"https?://[^\s<>'\"]+")
_MONTHLY_TITLE_RE = re.compile(
    r"who\s+is\s+hiring\?\s*\(\s*"
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+\d{4}\s*\)",
    re.IGNORECASE,
)

# HN "Who is hiring" headers follow a `Company | ... | ...` convention but
# the order beyond slot 0 is not standardized. We detect which slot is the
# title by ruling out the things a title is NOT: location, employment type,
# compensation, sponsorship policy.
_LOCATION_RE = re.compile(
    r"(?ix)"
    r"\b(?:remote|hybrid|on[\s\-]?site|wfh|in[\s\-]?office)\b"
    r"|\b(?:USA|UK|EU|EMEA|APAC|US|UK|EU only|world[\s\-]?wide|anywhere)\b"
    r"|\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s+(?:[A-Z]{2}|[A-Z][a-z]+)\b"  # City, ST or City, Country
)
_EMPLOYMENT_RE = re.compile(
    r"(?i)\b(?:full[\s\-]?time|part[\s\-]?time|contract|contractor|freelance|"
    r"intern(?:ship)?|temp|temporary|permanent|fte|c2c|w2)\b"
)
_COMP_RE = re.compile(r"(?i)\$|salary|comp(?:ensation)?|equity|\bk\b|/yr|/year")
_SPONSOR_RE = re.compile(r"(?i)visa|h[\s\-]?1b|sponsor|no\s+sponsor")
# Strong signal for "this slot is a job title" — most HN postings use one
# of these words. Used to prefer the right slot when the header is
# `Company | Description | Location | Title` rather than the textbook order.
_ROLE_KEYWORD_RE = re.compile(
    r"(?i)\b("
    r"engineer|engineering|developer|programmer|coder|"
    r"scientist|analyst|researcher|architect|designer|"
    r"manager|lead|director|head|chief|principal|staff|"
    r"founder|cto|cfo|ceo|vp|"
    r"intern(?:ship)?|consultant|specialist|advisor|"
    r"frontend|backend|full[\s\-]?stack|fullstack|"
    r"devops|sre|reliability|platform|infra(?:structure)?|"
    r"ml|ai|data|qa|test|security|"
    r"writer|editor|recruiter|operations"
    r")\b"
)


@register("hn_who_is_hiring")
def iter_postings(entry: WatchlistEntry, http: httpx.Client) -> Iterable[DiscoveredPosting]:
    try:
        story = _find_latest_thread(http)
    except httpx.HTTPError as exc:
        log.warning("hn search failed: %s", exc)
        return
    if not story:
        log.warning("hn: no matching 'Who is hiring' story found")
        return
    story_id = story["objectID"]
    story_title = story.get("title") or "Ask HN: Who is hiring?"
    log.info("hn: using story %s ('%s')", story_id, story_title)

    try:
        resp = http.get(_ITEM_URL_TPL.format(id=story_id))
        resp.raise_for_status()
        item = resp.json()
    except httpx.HTTPError as exc:
        log.warning("hn item fetch failed: %s", exc)
        return

    children = item.get("children") or []
    log.info("hn: %d top-level comments in thread", len(children))
    for kid in children:
        text = html_to_text(kid.get("text") or "")
        if not text:
            continue
        if not keyword_matches(text, entry.match_keywords):
            continue
        company, title, location = _parse_header(text)
        if not company:
            continue
        url = _extract_first_url(text) or f"https://news.ycombinator.com/item?id={kid.get('id')}"
        posted_at = parse_iso_date(kid.get("created_at"))
        # If the header carried a location (HN convention) but the body has
        # no "Location:" line, prepend one so the backend's parser captures
        # it. JobPosting.location is what the dashboard surfaces.
        if location and not re.search(r"(?im)^\s*location\s*:", text):
            text = f"Location: {location}\n\n{text}"
        yield DiscoveredPosting(
            company=company,
            title=title or "(see post)",
            url=url,
            raw_text=text,
            source=f"hn:{story_id}",
            posted_at=posted_at,
        )


def _find_latest_thread(http: httpx.Client) -> dict | None:
    """Find the most recent 'Ask HN: Who is hiring? (Month YYYY)' thread.

    Algolia's `/search` is relevance-ranked, which surfaces the
    high-upvote 2020 "Who is hiring right now?" thread instead of the
    current monthly one. `/search_by_date` is sorted by `created_at`
    desc, so the latest monthly thread is first.
    """
    resp = http.get(
        _SEARCH_BY_DATE_URL,
        params={
            "tags": "story,author_whoishiring",
            "query": "hiring",
            "hitsPerPage": 10,
        },
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    for hit in hits:
        title = hit.get("title") or ""
        if _MONTHLY_TITLE_RE.search(title):
            return hit
    return None


def _parse_header(comment_text: str) -> tuple[str, str, str]:
    """Return (company, title, location) from an HN hiring comment header.

    The first pipe slot is taken as the company. Remaining slots are
    classified: the first one matching a location pattern becomes the
    location, and the first slot that doesn't match location / employment
    type / compensation / sponsorship patterns becomes the title.
    """
    first_line = next((line.strip() for line in comment_text.splitlines() if line.strip()), "")
    if not first_line:
        return "", "", ""
    parts = [p.strip() for p in first_line.split("|") if p.strip()]
    if not parts:
        return "", "", ""
    company = parts[0]

    location = ""
    title = ""
    fallback_title = ""
    for slot in parts[1:]:
        is_location = bool(_LOCATION_RE.search(slot))
        is_employment = bool(_EMPLOYMENT_RE.search(slot))
        is_comp = bool(_COMP_RE.search(slot))
        is_sponsor = bool(_SPONSOR_RE.search(slot))
        is_long_prose = len(slot) > 80  # likely a company description, not a title
        if not location and is_location:
            location = slot
            continue
        if is_employment or is_comp or is_sponsor or is_location:
            continue
        # Strong signal: a role keyword wins regardless of slot order.
        if not title and _ROLE_KEYWORD_RE.search(slot):
            title = slot
            continue
        # Fallback: first non-disqualified, non-prose slot if no role keyword found.
        if not fallback_title and not is_long_prose:
            fallback_title = slot

    return company, title or fallback_title or "(see post)", location


def _extract_first_url(text: str) -> str:
    m = _URL_RE.search(text)
    return m.group(0).rstrip(".,;:)") if m else ""
