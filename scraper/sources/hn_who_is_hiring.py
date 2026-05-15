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
from scraper.sources._html import html_to_text
from scraper.sources._match import keyword_matches

log = logging.getLogger(__name__)

_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
_ITEM_URL_TPL = "https://hn.algolia.com/api/v1/items/{id}"
_URL_RE = re.compile(r"https?://[^\s<>'\"]+")


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
        company, title = _parse_header(text)
        if not company:
            continue
        url = _extract_first_url(text) or f"https://news.ycombinator.com/item?id={kid.get('id')}"
        yield DiscoveredPosting(
            company=company,
            title=title or "(see post)",
            url=url,
            raw_text=text,
            source=f"hn:{story_id}",
        )


def _find_latest_thread(http: httpx.Client) -> dict | None:
    resp = http.get(
        _SEARCH_URL,
        params={
            "tags": "story,author_whoishiring",
            "query": "hiring",
            "hitsPerPage": 10,
        },
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    for hit in hits:
        title = (hit.get("title") or "").lower()
        if "who is hiring" in title:
            return hit
    return None


def _parse_header(comment_text: str) -> tuple[str, str]:
    first_line = next((line.strip() for line in comment_text.splitlines() if line.strip()), "")
    if not first_line:
        return "", ""
    parts = [p.strip() for p in first_line.split("|") if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], ""
    return "", ""


def _extract_first_url(text: str) -> str:
    m = _URL_RE.search(text)
    return m.group(0).rstrip(".,;:)") if m else ""
