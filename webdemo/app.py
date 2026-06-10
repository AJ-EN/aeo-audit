"""Hosted demo for AEO Audit.

A thin FastAPI wrapper around ``aeo_audit.engine.ScanEngine`` that lets anyone
paste a URL and get a live scorecard — the zero-install on-ramp to the CLI.

Safety rails for a public endpoint:
  * SSRF guard   — only http(s); DNS-resolve the host and reject any private,
                   loopback, link-local, or reserved address (blocks cloud
                   metadata + internal services).
  * Rate limit   — per-IP token bucket (default 5 scans / hour).
  * Concurrency  — a global semaphore caps simultaneous scans so one cheap box
                   never gets stampeded into swapping.

The scan path itself is the exact same code the CLI runs, so the demo can never
disagree with `aeo-audit scan`.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from aeo_audit.core.models import CheckStatus, ScanResult
from aeo_audit.engine import ConfigLoader, ScanEngine

# --------------------------------------------------------------------------- #
# Tunables (overridable via env so the deploy can be throttled without a code
# change).
# --------------------------------------------------------------------------- #
MAX_CONCURRENT_SCANS = int(os.getenv("AEO_DEMO_CONCURRENCY", "2"))
RATE_LIMIT_PER_HOUR = int(os.getenv("AEO_DEMO_RATE_PER_HOUR", "5"))
SCAN_TIMEOUT_SECONDS = int(os.getenv("AEO_DEMO_SCAN_TIMEOUT", "60"))
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AEO Audit Demo", docs_url=None, redoc_url=None)

# The GitHub Pages landing site embeds the scan widget and calls this API
# cross-origin. Lock CORS to the origins that legitimately host the widget.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aj-en.github.io",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_methods=["POST", "GET"],
    allow_headers=["content-type"],
)

_scan_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCANS)
_config = ConfigLoader.load()

# In-memory rate limiter. Fine for a single small box; swap for Redis if this
# ever needs to scale horizontally.
_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    """Best-effort client IP, honoring a single proxy hop (Fly/railway)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(ip: str) -> bool:
    """Token-bucket check; records the hit when allowed."""
    now = time.monotonic()
    window = 3600.0
    bucket = _hits[ip]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_HOUR:
        return True
    bucket.append(now)
    return False


async def _validate_url(raw: str) -> tuple[str | None, str | None]:
    """Return (normalized_url, error). Blocks SSRF-prone targets."""
    raw = (raw or "").strip()
    if not raw:
        return None, "Please enter a URL."
    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return None, "Only http and https URLs are supported."
    host = parsed.hostname
    if not host:
        return None, "That doesn't look like a valid URL."
    if len(raw) > 2048:
        return None, "That URL is too long."

    # Resolve every address the host maps to and reject anything internal.
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return None, "Couldn't resolve that domain."

    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return None, "That address points to an internal/private host."

    return raw, None


def _shape_result(result: ScanResult) -> dict[str, Any]:
    """Trim a full ScanResult down to what the frontend renders.

    Mirrors the honest-grading contract: lead with score/100 + passes X/Y,
    label the percentile as a *rank of N sites*, surface a fix-list.
    """
    sc = result.scorecard

    categories = [
        {
            "name": cat.value,
            "score": round(cs.score, 1),
            "grade": cs.grade.value,
            "weight": cs.weight,
        }
        for cat, cs in sc.categories.items()
    ]
    categories.sort(key=lambda c: c["weight"], reverse=True)

    fixes = [
        {
            "name": r.name,
            "category": r.category.value,
            "status": r.status.value,
            "message": r.message,
        }
        for r in result.check_results
        if r.status in (CheckStatus.FAIL, CheckStatus.WARN)
    ]
    # Worst first: outright failures above warnings.
    fixes.sort(key=lambda f: 0 if f["status"] == "fail" else 1)

    passing = [
        r.name
        for r in result.check_results
        if r.status == CheckStatus.PASS
    ]

    return {
        "url": sc.url,
        "overall_score": round(sc.overall_score, 1),
        "grade": sc.grade.value,
        "passed_checks": sc.passed_checks,
        "total_checks": sc.total_checks,
        "percentile": round(sc.percentile, 0) if sc.percentile is not None else None,
        "benchmark_size": sc.benchmark_size,
        "confidence": {
            "lower": round(sc.confidence_interval.lower, 1),
            "upper": round(sc.confidence_interval.upper, 1),
        },
        "categories": categories,
        "fixes": fixes,
        "passing": passing,
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/scan")
async def scan(request: Request) -> JSONResponse:
    ip = _client_ip(request)
    if _rate_limited(ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": (
                    f"Rate limit reached ({RATE_LIMIT_PER_HOUR} scans/hour). "
                    "Install the CLI for unlimited local scans — it's the real product."
                )
            },
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid request body."})

    url, err = await _validate_url(str(body.get("url", "")))
    if err:
        return JSONResponse(status_code=400, content={"error": err})
    assert url is not None

    async with _scan_semaphore:
        try:
            result = await asyncio.wait_for(
                ScanEngine.scan(url, _config, no_cache=False),
                timeout=SCAN_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"error": "That site took too long to scan. Try the CLI locally."},
            )
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                status_code=502,
                content={"error": f"Scan failed: {exc}"},
            )

    return JSONResponse(content=_shape_result(result))


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Anything else under / falls through to static assets.
app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
