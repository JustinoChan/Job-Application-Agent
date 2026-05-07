from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.openclaw_adapter import (
    OpenClawError,
    ask_openclaw,
    extract_job_posting_with_openclaw,
    is_openclaw_available,
)


def _mock_process(stdout: str = "", stderr: str = "", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode())
    )
    proc.returncode = returncode
    proc.kill = MagicMock()
    return proc


def _openclaw_json(text: str) -> str:
    return json.dumps({
        "ok": True,
        "capability": "model.run",
        "transport": "gateway",
        "provider": "openai-codex",
        "model": "gpt-5.4-mini",
        "outputs": [{"text": text, "mediaUrl": None}],
    })


class TestIsOpenclawAvailable:
    def test_available(self):
        with patch("src.openclaw_adapter.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="openclaw v2026.5.4\n", stderr="")
            available, reason = is_openclaw_available()
            assert available is True
            assert "2026.5.4" in reason

    def test_not_found(self):
        with patch("src.openclaw_adapter.subprocess.run", side_effect=FileNotFoundError):
            available, reason = is_openclaw_available()
            assert available is False
            assert "not found" in reason

    def test_nonzero_exit(self):
        with patch("src.openclaw_adapter.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            available, reason = is_openclaw_available()
            assert available is False
            assert "code 1" in reason

    def test_timeout(self):
        with patch("src.openclaw_adapter.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("openclaw", 10)):
            available, reason = is_openclaw_available()
            assert available is False
            assert "timed out" in reason


class TestAskOpenclaw:
    @pytest.mark.asyncio
    async def test_success(self):
        proc = _mock_process(stdout=_openclaw_json("Hello world"))
        with patch("src.openclaw_adapter.asyncio.create_subprocess_exec", return_value=proc):
            result = await ask_openclaw("say hello")
            assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_nonzero_exit(self):
        proc = _mock_process(stdout="", stderr="gateway error", returncode=1)
        with patch("src.openclaw_adapter.asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(OpenClawError, match="exited with code 1"):
                await ask_openclaw("test")

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        proc = _mock_process(stdout="not json at all")
        with patch("src.openclaw_adapter.asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(OpenClawError, match="invalid JSON"):
                await ask_openclaw("test")

    @pytest.mark.asyncio
    async def test_ok_false(self):
        proc = _mock_process(stdout=json.dumps({"ok": False, "error": "bad"}))
        with patch("src.openclaw_adapter.asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(OpenClawError, match="ok=false"):
                await ask_openclaw("test")

    @pytest.mark.asyncio
    async def test_missing_outputs(self):
        proc = _mock_process(stdout=json.dumps({"ok": True}))
        with patch("src.openclaw_adapter.asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(OpenClawError, match="missing outputs"):
                await ask_openclaw("test")

    @pytest.mark.asyncio
    async def test_empty_text(self):
        data = json.dumps({"ok": True, "outputs": [{"text": ""}]})
        proc = _mock_process(stdout=data)
        with patch("src.openclaw_adapter.asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(OpenClawError, match="empty text"):
                await ask_openclaw("test")

    @pytest.mark.asyncio
    async def test_timeout(self):
        async def slow_create(*args, **kwargs):
            proc = AsyncMock()
            proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
            proc.kill = MagicMock()
            proc.returncode = -1
            return proc

        with patch("src.openclaw_adapter.asyncio.create_subprocess_exec", side_effect=slow_create):
            with pytest.raises(OpenClawError, match="timed out"):
                await ask_openclaw("test", timeout=0.01)

    @pytest.mark.asyncio
    async def test_command_not_found(self):
        with patch("src.openclaw_adapter.asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with pytest.raises(OpenClawError, match="not found"):
                await ask_openclaw("test")


class TestExtractJobPosting:
    @pytest.mark.asyncio
    async def test_extracts_job_text(self):
        extracted = "Job Title: Software Engineer\nCompany: TestCo"
        proc = _mock_process(stdout=_openclaw_json(extracted))
        with patch("src.openclaw_adapter.asyncio.create_subprocess_exec", return_value=proc):
            result = await extract_job_posting_with_openclaw("raw html content here")
            assert result == extracted
