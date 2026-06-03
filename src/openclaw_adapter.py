from __future__ import annotations

import asyncio
import json
import os
import subprocess


class OpenClawError(Exception):
    pass


DEFAULT_OPENCLAW_COMMAND = "openclaw"
# Empty by default: don't force a --model override. The gateway agent has its
# own allowed default model, and overriding it to a model the agent doesn't
# permit fails with "Model override ... is not allowed for agent". Set
# OPENCLAW_MODEL explicitly only to a model the gateway actually allows.
DEFAULT_OPENCLAW_MODEL = ""
DEFAULT_OPENCLAW_TIMEOUT = 60.0


def get_openclaw_command() -> str:
    return os.getenv("OPENCLAW_COMMAND", DEFAULT_OPENCLAW_COMMAND)


def get_openclaw_model() -> str:
    return os.getenv("OPENCLAW_MODEL", DEFAULT_OPENCLAW_MODEL).strip()


def get_openclaw_timeout() -> float:
    raw = os.getenv("OPENCLAW_TIMEOUT_SECONDS")
    if not raw:
        return DEFAULT_OPENCLAW_TIMEOUT
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_OPENCLAW_TIMEOUT


def _resolve_base_argv(command: str) -> list[str]:
    """Return the argv prefix used to launch OpenClaw.

    On Windows, npm installs OpenClaw as a `.cmd` shim that ultimately runs
    `node <entry>.mjs %*`. Passing our large JSON prompt through that shim
    makes cmd.exe re-parse the arguments: the JSON's own double quotes break
    cmd's quoting, so any `&` in the payload (e.g. a `&gh_jid=...` Greenhouse
    apply-URL parameter) is treated as a command separator — cmd then tries to
    run the trailing fragment as its own command and the call fails with
    "'gh_jid' is not recognized as an internal or external command". Invoking
    node + the entry script directly hands argv straight to node (standard C
    runtime parsing) so the prompt survives intact.
    """
    if os.name == "nt" and command.lower().endswith((".cmd", ".bat")):
        shim_dir = os.path.dirname(os.path.abspath(command))
        entry = os.path.join(shim_dir, "node_modules", "openclaw", "openclaw.mjs")
        if os.path.exists(entry):
            node = os.path.join(shim_dir, "node.exe")
            if not os.path.exists(node):
                node = "node"
            return [node, entry]
    return [command]


def is_openclaw_available() -> tuple[bool, str]:
    command = get_openclaw_command()
    try:
        result = subprocess.run(
            [command, "--version"],
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
    command = get_openclaw_command()
    model = get_openclaw_model()
    effective_timeout = timeout if timeout is not None else get_openclaw_timeout()
    args = _resolve_base_argv(command) + ["infer", "model", "run", "--gateway"]
    if model:
        # Only override the gateway agent's default model when explicitly
        # configured to an allowed model. Otherwise let the agent decide.
        args += ["--model", model]
    args += ["--prompt", prompt, "--json"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
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
