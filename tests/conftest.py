"""Shared test fixtures and configuration."""

from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer
from typing import Generator

import pytest

from aeo_audit.core.crawler import Crawler
from aeo_audit.core.models import (
    Category,
    CheckContext,
    CheckResult,
    CheckStatus,
    Config,
    Finding,
    Scorecard,
    Severity,
)
from tests.fixtures.server import PORT, MockAEOHandler


@pytest.fixture(scope="session")
def mock_server() -> Generator[str, None, None]:
    """Start and run the mock AEO server for integration testing."""
    server = ThreadingHTTPServer(("localhost", PORT), MockAEOHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield f"http://localhost:{PORT}"
    server.shutdown()
    thread.join()


@pytest.fixture
async def crawler() -> Generator[Crawler, None, None]:
    """Create a crawler instance for testing."""
    async with Crawler(cache_enabled=False) as c:
        yield c


@pytest.fixture
def sample_check_context() -> CheckContext:
    """Create a minimal CheckContext for testing."""
    return CheckContext(
        url="https://example.com",
        base_url="https://example.com",
        headers={},
        rendered_html="<html><body>Test</body></html>",
        raw_html="<html><body>Test</body></html>",
    )


@pytest.fixture
def sample_config() -> Config:
    """Create a minimal Config for testing."""
    return Config(
        weights={
            "discovery": 0.25,
            "identity": 0.15,
            "capabilities": 0.25,
            "commerce": 0.20,
            "trust": 0.15,
        },
        checks={
            "discovery": {"agent_manifest": 0.25, "mcp_endpoint": 0.20},
            "identity": {"did_document": 0.30},
            "capabilities": {"openapi_spec": 0.25},
            "commerce": {"agent_pricing_json": 0.30},
            "trust": {"audit_log_endpoint": 0.25},
        },
        thresholds={"grade_A": 90, "grade_B": 75, "grade_C": 60, "grade_D": 40},
    )


@pytest.fixture
def sample_finding() -> Finding:
    """Create a sample Finding for testing."""
    return Finding(
        title="Missing agent manifest",
        description="No agent-manifest.json found at /.well-known/",
        severity=Severity.HIGH,
        category=Category.DISCOVERY,
        check_name="agent_manifest",
        recommendation="Create a /.well-known/agent-manifest.json file",
    )
