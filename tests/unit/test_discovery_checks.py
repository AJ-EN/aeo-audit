"""Unit tests for discovery checks that need no network (context injected)."""

from __future__ import annotations

from typing import Any

import pytest

import aeo_audit.checks.discovery as discovery
from aeo_audit.checks.discovery import RobotsAgentCheck
from aeo_audit.core.models import CheckContext, CheckStatus


def _ctx(robots: str) -> CheckContext:
    # base_url points nowhere reachable; with robots_txt set, the self-fetch
    # fallback is never triggered, so these tests stay fully offline.
    return CheckContext(url="http://x/", base_url="http://x", robots_txt=robots)


class _FakeClient:
    """Minimal async httpx.AsyncClient stand-in for the self-fetch path."""

    def __init__(self, body: str | None) -> None:
        self._body = body

    def __call__(self, *args: Any, **kwargs: Any) -> _FakeClient:
        return self

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def get(self, *args: Any, **kwargs: Any) -> Any:
        if self._body is None:
            raise RuntimeError("network unavailable")
        return type("Resp", (), {"status_code": 200, "text": self._body})()


class TestRobotsAgentCheck:
    """Tiered crawlability scoring for robots.txt."""

    @pytest.mark.asyncio
    async def test_explicit_agent_allow_passes_full(self) -> None:
        result = await RobotsAgentCheck().run(
            _ctx("User-agent: GPTBot\nAllow: /\nUser-agent: agent\nAllow: /\n")
        )
        assert result.status == CheckStatus.PASS
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_allow_all_wildcard_passes_partial(self) -> None:
        # "User-agent: *" without disallowing root -> agents permitted (0.75).
        result = await RobotsAgentCheck().run(_ctx("User-agent: *\nDisallow:\n"))
        assert result.status == CheckStatus.PASS
        assert result.score == 0.75

    @pytest.mark.asyncio
    async def test_wildcard_disallow_root_fails(self) -> None:
        result = await RobotsAgentCheck().run(_ctx("User-agent: *\nDisallow: /\n"))
        assert result.status == CheckStatus.FAIL
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_named_agent_block_fails(self) -> None:
        result = await RobotsAgentCheck().run(_ctx("User-agent: GPTBot\nDisallow: /\n"))
        assert result.status == CheckStatus.FAIL

    @pytest.mark.asyncio
    async def test_agent_allow_overrides_wildcard_block(self) -> None:
        # A site can block generic crawlers but still welcome named agents.
        robots = "User-agent: *\nDisallow: /\nUser-agent: GPTBot\nAllow: /\n"
        result = await RobotsAgentCheck().run(_ctx(robots))
        assert result.status == CheckStatus.PASS
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_non_agent_directives_only_warns(self) -> None:
        # robots only mentions a search bot; agents are not addressed.
        result = await RobotsAgentCheck().run(_ctx("User-agent: Googlebot\nDisallow: /private\n"))
        assert result.status == CheckStatus.WARN
        assert result.score == 0.5

    @pytest.mark.asyncio
    async def test_invalid_body_fails(self) -> None:
        # A 404 / HTML body with no user-agent directives is not a robots.txt.
        result = await RobotsAgentCheck().run(_ctx('{"error": "Not Found"}'))
        assert result.status == CheckStatus.FAIL
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_self_fetch_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # robots_txt is None -> the check fetches /robots.txt itself.
        monkeypatch.setattr(discovery.httpx, "AsyncClient", _FakeClient("User-agent: *\nDisallow:\n"))
        ctx = CheckContext(url="http://x/", base_url="http://x", robots_txt=None)
        result = await RobotsAgentCheck().run(ctx)
        assert result.status == CheckStatus.PASS
        assert result.score == 0.75

    @pytest.mark.asyncio
    async def test_self_fetch_failure_falls_back_to_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Self-fetch raises -> no robots data -> FAIL (no crawl guidance).
        monkeypatch.setattr(discovery.httpx, "AsyncClient", _FakeClient(None))
        ctx = CheckContext(url="http://x/", base_url="http://x", robots_txt=None)
        result = await RobotsAgentCheck().run(ctx)
        assert result.status == CheckStatus.FAIL
        assert result.score == 0.0
