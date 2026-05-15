"""Source adapters. Each module registers itself in REGISTRY via @register."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import httpx

from scraper.api_client import DiscoveredPosting


@dataclass(frozen=True)
class WatchlistEntry:
    kind: str
    company_slug: str | None = None
    match_titles: list[str] | None = None
    match_keywords: list[str] | None = None
    label: str | None = None

    @property
    def display(self) -> str:
        if self.label:
            return self.label
        if self.company_slug:
            return f"{self.kind}:{self.company_slug}"
        return self.kind


SourceFn = Callable[[WatchlistEntry, httpx.Client], Iterable[DiscoveredPosting]]
REGISTRY: dict[str, SourceFn] = {}


def register(name: str):
    def deco(fn: SourceFn) -> SourceFn:
        REGISTRY[name] = fn
        return fn
    return deco


# Trigger registration of adapters on package import.
from scraper.sources import greenhouse, lever, ashby, hn_who_is_hiring  # noqa: F401,E402
