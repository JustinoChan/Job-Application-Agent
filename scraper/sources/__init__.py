"""Source adapters. Each module registers itself in REGISTRY via @register."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

import httpx

from scraper.api_client import DiscoveredPosting
from scraper.politeness import Politeness


@dataclass(frozen=True)
class WatchlistEntry:
    kind: str
    company_slug: str | None = None
    match_titles: list[str] | None = None
    match_keywords: list[str] | None = None
    label: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def display(self) -> str:
        if self.label:
            return self.label
        if self.company_slug:
            return f"{self.kind}:{self.company_slug}"
        return self.kind


# Adapters take a httpx.Client (for connection reuse) plus a Politeness
# instance that enforces inter-request delays and retries globally.
SourceFn = Callable[[WatchlistEntry, httpx.Client, Politeness], Iterable[DiscoveredPosting]]
REGISTRY: dict[str, SourceFn] = {}


def register(name: str):
    def deco(fn: SourceFn) -> SourceFn:
        REGISTRY[name] = fn
        return fn
    return deco


# Trigger registration of adapters on package import.
from scraper.sources import greenhouse, lever, ashby, hn_who_is_hiring, workday  # noqa: F401,E402
