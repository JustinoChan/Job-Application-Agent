"""Discord webhook notifications for high-fit job discoveries.

Sends a rich embed to a Discord channel when a job lands above the
configured fit threshold. Designed to be fire-and-forget — failures
are logged but never block the discover pipeline.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import httpx

log = logging.getLogger(__name__)

_WEBHOOK_URL: str | None = None
_FIT_THRESHOLD: float = 0.5
_PING_USER_ID: str | None = None
_LOADED = False


def _load_config() -> None:
    global _WEBHOOK_URL, _FIT_THRESHOLD, _PING_USER_ID, _LOADED
    if _LOADED:
        return
    _WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip() or None
    try:
        _FIT_THRESHOLD = float(os.getenv("NOTIFICATION_FIT_THRESHOLD", "0.5"))
    except ValueError:
        _FIT_THRESHOLD = 0.5
    _PING_USER_ID = os.getenv("DISCORD_PING_USER_ID", "").strip() or None
    _LOADED = True


def is_enabled() -> bool:
    _load_config()
    return _WEBHOOK_URL is not None


def should_notify(fit_score: float) -> bool:
    _load_config()
    return _WEBHOOK_URL is not None and fit_score >= _FIT_THRESHOLD


def _rec_color(recommendation: str) -> int:
    return {
        "strong": 0x047857,
        "moderate": 0x1D4ED8,
        "weak": 0xC2410C,
    }.get(recommendation, 0x57534E)


def _rec_emoji(recommendation: str) -> str:
    return {
        "strong": "\U0001f525",
        "moderate": "✅",
        "weak": "\U0001f7e1",
    }.get(recommendation, "")


def send_new_job_notification(
    *,
    job_id: str,
    company: str,
    title: str,
    fit_score: float,
    recommendation: str,
    url: str | None = None,
    location: str | None = None,
    experience_level: str | None = None,
    source: str | None = None,
    auto_tailored: bool = False,
    dashboard_base_url: str | None = None,
) -> bool:
    _load_config()
    if not _WEBHOOK_URL:
        return False

    emoji = _rec_emoji(recommendation)
    color = _rec_color(recommendation)

    fields = [
        {"name": "Fit Score", "value": f"**{fit_score:.0%}** ({recommendation})", "inline": True},
    ]
    if location:
        fields.append({"name": "Location", "value": location, "inline": True})
    if experience_level:
        fields.append({"name": "Level", "value": experience_level, "inline": True})
    if source:
        fields.append({"name": "Source", "value": source, "inline": True})
    if auto_tailored:
        fields.append({"name": "Resume", "value": "✅ Auto-generated", "inline": True})

    links: list[str] = []
    if url:
        links.append(f"[\U0001f517 Job Posting]({url})")
    if dashboard_base_url:
        links.append(f"[\U0001f4cb Dashboard](https://{dashboard_base_url}/job/{job_id})")
    if links:
        fields.append({"name": "Links", "value": " • ".join(links), "inline": False})

    embed = {
        "title": f"{emoji} {company} — {title}",
        "color": color,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Job Application Agent"},
    }

    ping = f"<@{_PING_USER_ID}>" if _PING_USER_ID else ""
    payload = {"content": ping, "embeds": [embed]}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(_WEBHOOK_URL, json=payload)
            resp.raise_for_status()
        log.info("discord notification sent for %s (%s / %s)", job_id, company, title)
        return True
    except Exception:
        log.exception("failed to send discord notification for %s", job_id)
        return False
