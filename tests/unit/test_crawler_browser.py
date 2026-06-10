"""Unit tests for the crawler's first-run browser auto-install path."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aeo_audit.core.crawler import Crawler


@pytest.mark.asyncio
async def test_auto_installs_chromium_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing browser triggers `playwright install chromium`, then retries."""
    crawler = Crawler(cache_enabled=False)
    browser = object()
    launch = AsyncMock(side_effect=[Exception("Executable doesn't exist at /x"), browser])
    crawler._playwright = MagicMock()
    crawler._playwright.chromium.launch = launch

    calls: dict[str, Any] = {}
    monkeypatch.setattr(subprocess, "run", lambda cmd, check: calls.setdefault("cmd", cmd))

    result = await crawler._launch_chromium()

    assert result is browser
    assert launch.call_count == 2  # failed once, succeeded after install
    assert "playwright" in calls["cmd"] and "install" in calls["cmd"]


@pytest.mark.asyncio
async def test_unrelated_launch_error_is_reraised() -> None:
    """A non-browser launch error must propagate, not trigger an install."""
    crawler = Crawler(cache_enabled=False)
    crawler._playwright = MagicMock()
    crawler._playwright.chromium.launch = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await crawler._launch_chromium()


@pytest.mark.asyncio
async def test_clear_message_when_autoinstall_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """If auto-install fails, surface an actionable instruction."""
    crawler = Crawler(cache_enabled=False)
    crawler._playwright = MagicMock()
    crawler._playwright.chromium.launch = AsyncMock(side_effect=Exception("Executable doesn't exist"))

    def _boom(cmd: Any, check: Any) -> None:
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", _boom)

    with pytest.raises(RuntimeError, match="playwright install chromium"):
        await crawler._launch_chromium()
