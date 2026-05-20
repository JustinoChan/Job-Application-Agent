"""Browser form-filling for Greenhouse and Lever apply pages.

Uses Playwright to open the apply page in a real browser, pre-fill
personal information from the master profile, attach the latest
tailored resume PDF, then **pause** so the user can review and click
Submit themselves. We never auto-submit.

Supported ATS platforms:
  - Greenhouse (boards.greenhouse.io)
  - Lever      (jobs.lever.co)

Usage from the API:
    result = await prefill_application(job_id, profile)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from src import config, tracker
from src.models import MasterProfile

log = logging.getLogger(__name__)


@dataclass
class PrefillResult:
    job_id: str
    url: str
    fields_filled: list[str] = field(default_factory=list)
    resume_attached: bool = False
    paused: bool = False
    error: str | None = None


def _detect_ats(url: str) -> str | None:
    low = url.lower()
    if "greenhouse.io" in low or "boards.greenhouse" in low:
        return "greenhouse"
    if "lever.co" in low or "jobs.lever" in low:
        return "lever"
    return None


def _latest_resume_pdf(job_id: str) -> Path | None:
    version = config.next_resume_version(job_id) - 1
    if version < 1:
        return None
    paths = config.version_paths(job_id, version)
    pdf = paths["pdf"]
    if pdf.exists():
        return pdf
    html = paths["html"]
    if html.exists():
        return html
    return None


async def _fill_greenhouse(page, profile: MasterProfile, resume_path: Path | None) -> list[str]:
    filled: list[str] = []

    field_map = {
        "#first_name": profile.name.split()[0] if profile.name else "",
        "#last_name": " ".join(profile.name.split()[1:]) if profile.name else "",
        "#email": profile.email or "",
        "#phone": getattr(profile, "phone", "") or "",
    }

    for selector, value in field_map.items():
        if not value:
            continue
        try:
            el = page.locator(selector)
            if await el.count() > 0:
                await el.fill(value)
                filled.append(selector)
        except Exception:
            pass

    location_val = profile.location or ""
    if location_val:
        for sel in ["#job_application_location", "input[name*='location']"]:
            try:
                el = page.locator(sel)
                if await el.count() > 0:
                    await el.fill(location_val)
                    filled.append("location")
                    break
            except Exception:
                pass

    if resume_path and resume_path.exists():
        for sel in ["input[type='file']", "#resume_file", "input[name*='resume']"]:
            try:
                el = page.locator(sel)
                if await el.count() > 0:
                    await el.set_input_files(str(resume_path))
                    filled.append("resume")
                    break
            except Exception:
                pass

    education = profile.education[0] if getattr(profile, "education", None) else None
    if education:
        school = getattr(education, "school", "") or (education.get("school", "") if isinstance(education, dict) else "")
        degree = getattr(education, "degree", "") or (education.get("degree", "") if isinstance(education, dict) else "")
        for sel in ["input[name*='school']", "#education_school_name_0"]:
            try:
                el = page.locator(sel)
                if await el.count() > 0 and school:
                    await el.fill(school)
                    filled.append("school")
                    break
            except Exception:
                pass
        for sel in ["input[name*='degree']", "#education_degree_0"]:
            try:
                el = page.locator(sel)
                if await el.count() > 0 and degree:
                    await el.fill(degree)
                    filled.append("degree")
                    break
            except Exception:
                pass

    return filled


async def _fill_lever(page, profile: MasterProfile, resume_path: Path | None) -> list[str]:
    filled: list[str] = []

    field_map = {
        "input[name='name']": profile.name or "",
        "input[name='email']": profile.email or "",
        "input[name='phone']": getattr(profile, "phone", "") or "",
        "input[name='org']": "",
        "input[name='urls[LinkedIn]']": getattr(profile, "linkedin", "") or "",
        "input[name='urls[GitHub]']": getattr(profile, "github", "") or "",
    }

    for selector, value in field_map.items():
        if not value:
            continue
        try:
            el = page.locator(selector)
            if await el.count() > 0:
                await el.fill(value)
                filled.append(selector.split("'")[1] if "'" in selector else selector)
        except Exception:
            pass

    location_val = profile.location or ""
    if location_val:
        try:
            el = page.locator("input[name='location']")
            if await el.count() > 0:
                await el.fill(location_val)
                filled.append("location")
        except Exception:
            pass

    if resume_path and resume_path.exists():
        try:
            el = page.locator("input[type='file']")
            if await el.count() > 0:
                await el.set_input_files(str(resume_path))
                filled.append("resume")
        except Exception:
            pass

    return filled


async def prefill_application(
    job_id: str,
    profile: MasterProfile,
    *,
    url_override: str | None = None,
    headless: bool = False,
) -> PrefillResult:
    """Open the apply page, pre-fill fields, attach resume, then pause.

    The browser stays open so the user can review, fix anything, and
    click Submit themselves. Returns once the page is loaded and filled.
    """
    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    url = url_override or (entry.url if entry else None)
    if not url:
        return PrefillResult(job_id=job_id, url="", error="No apply URL found")

    ats = _detect_ats(url)
    if not ats:
        return PrefillResult(job_id=job_id, url=url, error=f"Unsupported ATS platform for URL: {url}")

    resume_path = _latest_resume_pdf(job_id)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return PrefillResult(
            job_id=job_id, url=url,
            error="Playwright not installed. Run: pip install playwright && python -m playwright install chromium",
        )

    result = PrefillResult(job_id=job_id, url=url)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            apply_url = url
            if ats == "greenhouse" and "/apply" not in url:
                apply_url = url.rstrip("/") + "/apply"
            elif ats == "lever" and "/apply" not in url:
                apply_url = url.rstrip("/") + "/apply"

            await page.goto(apply_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1500)

            if ats == "greenhouse":
                result.fields_filled = await _fill_greenhouse(page, profile, resume_path)
            elif ats == "lever":
                result.fields_filled = await _fill_lever(page, profile, resume_path)

            result.resume_attached = "resume" in result.fields_filled
            result.paused = True

            log.info(
                "browser prefill done for %s — filled %d fields, resume=%s, waiting for user",
                job_id, len(result.fields_filled), result.resume_attached,
            )

            await page.pause()
            await browser.close()

    except Exception as exc:
        result.error = str(exc)
        log.exception("browser prefill failed for %s", job_id)

    return result
