from __future__ import annotations

import asyncio
import json
import os
import subprocess


class OpenClawError(Exception):
    pass


OPENCLAW_COMMAND = os.getenv("OPENCLAW_COMMAND", "openclaw")
OPENCLAW_MODEL = os.getenv("OPENCLAW_MODEL", "openai-codex/gpt-5.4-mini")
OPENCLAW_TIMEOUT = float(os.getenv("OPENCLAW_TIMEOUT_SECONDS", "60"))


def is_openclaw_available() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [OPENCLAW_COMMAND, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            return True, version or "openclaw available"
        return False, f"openclaw exited with code {result.returncode}"
    except FileNotFoundError:
        return False, "openclaw command not found"
    except subprocess.TimeoutExpired:
        return False, "openclaw --version timed out"
    except OSError as exc:
        return False, str(exc)


async def ask_openclaw(prompt: str, *, timeout: float | None = None) -> str:
    effective_timeout = timeout if timeout is not None else OPENCLAW_TIMEOUT
    try:
        proc = await asyncio.create_subprocess_exec(
            OPENCLAW_COMMAND,
            "infer", "model", "run",
            "--gateway",
            "--model", OPENCLAW_MODEL,
            "--prompt", prompt,
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=effective_timeout
        )
    except FileNotFoundError:
        raise OpenClawError("openclaw command not found")
    except asyncio.TimeoutError:
        proc.kill()
        raise OpenClawError(
            f"OpenClaw timed out after {effective_timeout}s"
        )

    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        raise OpenClawError(f"OpenClaw exited with code {proc.returncode}: {err}")

    raw = stdout.decode(errors="replace").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpenClawError(f"OpenClaw returned invalid JSON: {exc}") from exc

    if not data.get("ok"):
        raise OpenClawError(f"OpenClaw returned ok=false: {raw[:500]}")

    outputs = data.get("outputs")
    if not outputs or not isinstance(outputs, list):
        raise OpenClawError("OpenClaw response missing outputs array")

    text = outputs[0].get("text")
    if not text:
        raise OpenClawError("OpenClaw returned empty text output")

    return text.strip()


def _extraction_prompt(text: str, source_url: str | None = None) -> str:
    source = f"Source URL: {source_url}\n" if source_url else "Source URL: not provided\n"
    return (
        f"{source}"
        "Task: Extract only the job posting content from the source page/text below. "
        "Return the job title, company, location, responsibilities, requirements, "
        "and nice-to-haves. Preserve bullet formatting. Do not add commentary.\n\n"
        "Page text:\n"
        f"{text[:30000]}"
    )


async def extract_job_posting_with_openclaw(raw_text: str, source_url: str | None = None) -> str:
    return await ask_openclaw(_extraction_prompt(raw_text, source_url=source_url))
