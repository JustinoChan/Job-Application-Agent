from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 20.0
MAX_REDIRECTS = 5
MAX_RETRIES = 3

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class UnsafeUrlError(ValueError):
    pass


@dataclass(frozen=True)
class ScrapedJob:
    raw_text: str
    final_url: str


def validate_url(url: str) -> None:
    """Raise UnsafeUrlError if URL is unsafe for server-side fetching."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("Only http and https URLs are allowed.")
    if not parsed.hostname:
        raise UnsafeUrlError("URL must include a hostname.")

    host = parsed.hostname.strip().lower()
    if host in {"localhost", "0.0.0.0"}:
        raise UnsafeUrlError("Localhost URLs are not allowed.")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ips = _resolve_host(host)
    else:
        ips = [ip]

    for ip in ips:
        if _is_blocked_ip(ip):
            raise UnsafeUrlError(f"Blocked private or reserved address: {ip}")


def _resolve_host(hostname: str) -> list[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Could not resolve hostname: {hostname}") from exc

    addresses = []
    for info in infos:
        address = info[4][0]
        try:
            addresses.append(ipaddress.ip_address(address))
        except ValueError:
            continue
    if not addresses:
        raise UnsafeUrlError(f"No usable IP addresses found for: {hostname}")
    return addresses


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def fetch_page(url: str) -> ScrapedJob:
    import asyncio

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        if attempt > 0:
            await asyncio.sleep(2 ** attempt)
        try:
            return await _fetch_page_once(url)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            continue
    raise ValueError(f"Failed after {MAX_RETRIES} retries: {last_error}")


async def _fetch_page_once(url: str) -> ScrapedJob:
    current_url = url
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={
            "User-Agent": _BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        },
        follow_redirects=False,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            validate_url(current_url)
            response = await client.get(current_url)

            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Redirect response did not include a Location header.")
                current_url = urljoin(current_url, location)
                continue

            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type and "text/plain" not in content_type:
                raise ValueError(f"Expected HTML/text response, got: {content_type or 'unknown'}")

            content = response.content
            if len(content) > MAX_RESPONSE_BYTES:
                raise ValueError("Response exceeded 5 MB limit.")

            text = _html_to_text(content.decode(response.encoding or "utf-8", errors="replace"))

            if _is_bot_blocked(text):
                raise ValueError(
                    "Page appears to be bot-blocked (anti-bot protection detected). "
                    "Try pasting the job description manually instead."
                )

            return ScrapedJob(raw_text=text, final_url=str(response.url))

    raise ValueError("Too many redirects while fetching job posting.")


def _is_bot_blocked(text: str) -> bool:
    lower = text.lower()
    indicators = [
        "please verify you are a human",
        "access denied",
        "enable javascript",
        "please enable cookies",
        "captcha",
        "cloudflare",
        "checking your browser",
        "just a moment",
        "ray id",
    ]
    matches = sum(1 for i in indicators if i in lower)
    return matches >= 2 or (len(text) < 500 and matches >= 1)


async def scrape_job_url(url: str, provider: str | None = None) -> str:
    scraped = await fetch_page(url)
    return await extract_job_posting(
        scraped.raw_text,
        provider=provider or os.getenv("LLM_PROVIDER", "none"),
        source_url=scraped.final_url,
    )


async def extract_job_posting(
    raw_html_text: str,
    provider: str = "none",
    source_url: str | None = None,
) -> str:
    cleaned = _clean_text(raw_html_text)
    provider = provider.lower().strip()
    if provider in {"", "none"}:
        return cleaned
    if provider == "openai":
        return await _extract_with_openai(cleaned)
    if provider == "anthropic":
        return await _extract_with_anthropic(cleaned)
    if provider == "openclaw":
        from src.openclaw_adapter import extract_job_posting_with_openclaw
        return await extract_job_posting_with_openclaw(cleaned, source_url=source_url)
    raise ValueError(f"Unsupported LLM provider: {provider}")


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return soup.get_text("\n")


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    compact = [line for line in lines if line]
    return "\n".join(compact)


def _extraction_prompt(text: str) -> str:
    return (
        "Extract only the job posting content from this page. Return the job title, "
        "company, location, responsibilities, requirements, and nice-to-haves. "
        "Preserve bullet formatting. Do not add commentary.\n\n"
        f"{text[:30000]}"
    )


async def _extract_with_openai(text: str) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = await client.responses.create(
        model=os.getenv("OPENAI_JOB_EXTRACT_MODEL", "gpt-5.5"),
        input=_extraction_prompt(text),
    )
    return response.output_text.strip()


async def _extract_with_anthropic(text: str) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = await client.messages.create(
        model=os.getenv("ANTHROPIC_JOB_EXTRACT_MODEL", "claude-3-5-sonnet-latest"),
        max_tokens=4000,
        messages=[{"role": "user", "content": _extraction_prompt(text)}],
    )
    return "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()
