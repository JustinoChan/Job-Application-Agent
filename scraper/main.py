"""Job-discovery scraper.

Loads a watchlist, dispatches each entry to its source adapter, and POSTs
discovered postings to /api/applications/discover. The discover endpoint is
idempotent, so re-runs of unchanged postings short-circuit to status=exists.
"""
from __future__ import annotations

import argparse
import logging
import sys

import httpx
import yaml

from scraper.api_client import ApiClient, DiscoveredPosting
from scraper.config import ScraperConfig, load_config
from scraper.sources import REGISTRY, WatchlistEntry

log = logging.getLogger("scraper")


SELF_TEST_POSTING = DiscoveredPosting(
    company="SelfTestCo",
    title="Software Engineer",
    url="https://example.com/jobs/self-test",
    raw_text=(
        "Software Engineer at SelfTestCo\n\n"
        "We're hiring a software engineer to build web applications.\n\n"
        "Requirements\n"
        "- Bachelor's degree in Computer Science or related\n"
        "- Experience with Python and React\n"
        "- Familiarity with SQL databases\n"
        "- Comfortable with Git\n\n"
        "Nice to Have\n"
        "- Experience with Django\n"
        "- Cloud platform exposure\n"
    ),
    source="self-test",
)


def _load_watchlist(config: ScraperConfig) -> list[WatchlistEntry]:
    if not config.watchlist_path.exists():
        log.warning("Watchlist not found at %s; nothing to scrape yet", config.watchlist_path)
        return []
    with config.watchlist_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    defaults = raw.get("defaults") or {}
    default_titles = defaults.get("match_titles") or None
    default_keywords = defaults.get("match_keywords") or None

    sources = raw.get("sources") or []
    entries: list[WatchlistEntry] = []
    for idx, src in enumerate(sources):
        if not isinstance(src, dict) or "kind" not in src:
            log.warning("watchlist[%d] is missing 'kind'; skipping", idx)
            continue
        entries.append(WatchlistEntry(
            kind=src["kind"],
            company_slug=src.get("company_slug"),
            match_titles=src.get("match_titles") or default_titles,
            match_keywords=src.get("match_keywords") or default_keywords,
            label=src.get("label"),
        ))
    return entries


def _scrape_sources(entries: list[WatchlistEntry], http: httpx.Client) -> list[DiscoveredPosting]:
    out: list[DiscoveredPosting] = []
    for entry in entries:
        fn = REGISTRY.get(entry.kind)
        if not fn:
            log.warning("unknown source kind '%s' for %s; skipping", entry.kind, entry.display)
            continue
        try:
            items = list(fn(entry, http))
        except Exception:
            log.exception("source %s failed", entry.display)
            continue
        log.info("source %s yielded %d posting(s)", entry.display, len(items))
        out.extend(items)
    return out


def run(self_test: bool = False) -> int:
    config = load_config()
    log.info("scraper start  api=%s  dry_run=%s", config.api_base_url, config.dry_run)
    api = ApiClient(config)
    if not config.dry_run:
        try:
            api.health()
        except Exception as exc:
            log.error("health check failed: %s", exc)
            return 2

    postings: list[DiscoveredPosting] = []
    if self_test:
        postings.append(SELF_TEST_POSTING)

    entries = _load_watchlist(config)
    if entries:
        with httpx.Client(
            headers={"User-Agent": config.user_agent},
            timeout=config.request_timeout_seconds,
        ) as http:
            postings.extend(_scrape_sources(entries, http))

    if not postings:
        log.info("no postings to send; exiting cleanly")
        api.close()
        return 0

    sent = 0
    skipped = 0
    saved = 0
    exists = 0
    failed = 0
    for posting in postings:
        try:
            result = api.discover(posting)
        except Exception as exc:
            log.error("discover failed for %s / %s: %s", posting.company, posting.title, exc)
            failed += 1
            continue
        sent += 1
        if result.status == "saved":
            saved += 1
            log.info("saved %s (fit=%.2f, rec=%s)", result.job_id, result.fit_score or 0.0, result.recommendation)
        elif result.status == "exists":
            exists += 1
            log.debug("exists %s (already in tracker)", result.job_id)
        elif result.status == "skipped":
            skipped += 1
            log.debug("skipped %s (%s)", result.job_id, result.reason)
        elif result.status == "dry-run":
            log.debug("dry-run %s", result.reason)

    log.info(
        "scraper done  sent=%d saved=%d exists=%d skipped=%d failed=%d",
        sent, saved, exists, skipped, failed,
    )
    api.close()
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Job-Application-Agent scraper")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Send one synthetic posting to verify the API pipeline end-to-end",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    )
    return run(self_test=args.self_test)


if __name__ == "__main__":
    sys.exit(main())
