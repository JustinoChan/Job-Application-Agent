"""URL extraction helpers shared by source adapters.

HN comments routinely append footnote markers like `[2]` after URLs;
prose elsewhere often wraps URLs in parentheses or trails them with
punctuation. A naive `[^\\s]+` regex captures all of that, producing
URLs that 404 (e.g. `https://grnh.se/b6ff87e61us[2]`). These helpers
extract URLs while excluding bracket characters and stripping trailing
punctuation in a paren-balanced way.
"""
from __future__ import annotations

import re

# Brackets are excluded from the URL body — HN footnote markers like
# `[2]` are the most common case where they appear adjacent to a URL.
_URL_RE = re.compile(r"https?://[^\s<>'\"\[\]]+")
_TRAILING_PUNCT = ".,;:!?"


def clean_url(url: str) -> str:
    """Strip trailing punctuation and unbalanced closing parens."""
    if not url:
        return ""
    url = url.strip()
    while url and url[-1] in _TRAILING_PUNCT:
        url = url[:-1]
    # Paren-balance: if there are more `)` than `(` in the URL, strip
    # trailing `)`. Keeps Wikipedia-style `Foo_(bar)` intact while
    # cleaning up `(https://example.com/foo)`.
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1]
    while url and url[-1] in _TRAILING_PUNCT:
        url = url[:-1]
    return url


def extract_first_url(text: str) -> str:
    m = _URL_RE.search(text or "")
    return clean_url(m.group(0)) if m else ""


def extract_urls(text: str, *, limit: int = 10) -> list[str]:
    """Return up to `limit` distinct cleaned URLs in order of first appearance."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _URL_RE.finditer(text or ""):
        u = clean_url(m.group(0))
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= limit:
            break
    return out
