"""Job-discovery scraper.

For step 1, this only supports a `--self-test` mode that posts a single
synthetic job to /api/applications/discover. Real source adapters land in step 2.
"""
from __future__ import annotations

import argparse
import logging
import sys

import yaml

from scraper.api_client import ApiClient, DiscoveredPosting
from scraper.config import ScraperConfig, load_config

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


def _iter_watchlist(config: ScraperConfig) -> list[DiscoveredPosting]:
    """Step-1 stub: returns no postings. Step 2 will dispatch by `kind`."""
    if not config.watchlist_path.exists():
        log.warning("Watchlist not found at %s; nothing to scrape yet", config.watchlist_path)
        return []
    with config.watchlist_path.open("r", encoding="utf-8") as f:
        watchlist = yaml.safe_load(f) or {}
    sources = watchlist.get("sources", [])
    if sources:
        log.info("Watchlist has %d source(s); adapters not implemented yet (step 2)", len(sources))
    else:
        log.info("Watchlist has no sources configured yet")
    return []


def run(self_test: bool = False) -> int:
    config = load_config()
    log.info("scraper start  api=%s  dry_run=%s", config.api_base_url, config.dry_run)
    client = ApiClient(config)
    try:
        client.health()
    except Exception as exc:
        log.error("health check failed: %s", exc)
        return 2

    postings: list[DiscoveredPosting] = []
    if self_test:
        postings.append(SELF_TEST_POSTING)
    postings.extend(_iter_watchlist(config))

    if not postings:
        log.info("no postings to send; exiting cleanly")
        return 0

    sent = 0
    skipped = 0
    saved = 0
    exists = 0
    failed = 0
    for posting in postings:
        try:
            result = client.discover(posting)
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
            log.info("exists %s (already in tracker)", result.job_id)
        elif result.status == "skipped":
            skipped += 1
            log.info("skipped %s (%s)", result.job_id, result.reason)
        elif result.status == "dry-run":
            log.info("dry-run %s", result.reason)

    log.info(
        "scraper done  sent=%d saved=%d exists=%d skipped=%d failed=%d",
        sent, saved, exists, skipped, failed,
    )
    client.close()
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
