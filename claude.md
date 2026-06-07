# AEO Audit CLI - Project Context

## Mission
Production-ready CLI tool (`aeo-audit`) that scans websites and scores their **Agent/Engine Optimization (AEO) readiness** (0-100) across 5 dimensions: Discovery, Identity, Capabilities, Commerce, Trust.

## Architecture Rules
1. **Type everything**: `mypy --strict` must pass on all source files.
2. **Async-first**: All checks and crawling are async (asyncio + Playwright).
3. **Config-driven**: All weights, thresholds, timeouts in `config.yaml`, overridable via CLI.
4. **Plugin system**: Checks auto-discovered via entry points (`aeo_audit.checks` group).
5. **TDD**: Write test first, then implement. Golden master for scoring.
6. **Single browser context**: Reuse Playwright context per scan, not per check.
7. **Cache everything**: SQLite cache keyed by `(url, user_agent, accept_header)`.
8. **Respect servers**: Honor `robots.txt`, `Crawl-Delay`, `RateLimit-*`, `Retry-After`.

## Tech Stack
- Python 3.11+ | Click | Rich | Pydantic v2
- Playwright (headless Chromium) | httpx | extruct
- openapi-spec-validator | jsonschema | dnspython
- Jinja2 + WeasyPrint | pytest + pytest-asyncio + hypothesis
- Hatch (build) | PyInstaller (binary)

## Scoring Algorithm
1. Each check -> `raw_score` (0.0-1.0)
2. Category score = weighted average of check scores
3. Overall = weighted average of 5 category scores
4. Normalize to 0-100 with percentile adjustment
5. Bootstrap 1000 samples -> 95% CI
6. Grade: A>=90, B>=75, C>=60, D>=40, F<40

## Category Weights
| Category     | Weight |
|-------------|--------|
| Discovery   | 0.25   |
| Identity    | 0.15   |
| Capabilities| 0.25   |
| Commerce    | 0.20   |
| Trust       | 0.15   |

## Design Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-07 | Hatch over Poetry | Lighter, PEP 621 native, faster builds |
| 2026-06-07 | Pydantic v2 strict mode | Runtime validation + mypy compatibility |
| 2026-06-07 | SQLite for cache | Zero-dependency, single-file, fast reads |
| 2026-06-07 | httpx over aiohttp | Better typing, HTTP/2 support, simpler API |
| 2026-06-07 | Mock Server Setup | Config-driven standard library HTTP server for integration testing |
| 2026-06-07 | Phase 3 Hardening | Secure CLI, asynchronous reporters, robust caching, packaging, docs |

## Current State
- **Phase**: 3 - Production Hardening & Polish (Completed)
- **Completed**: All 26 checks, 4 advanced reporters (HTML, PDF, Rich Terminal, JSON), SQLite cache caching mechanism, CLI subcommand architecture (scan, batch, diff, config, monitor), Homebrew generation setup, installer script, Hatch packaging configurations, and PyInstaller specifications with hidden imports are 100% complete.
- **In Progress**: None.
- **Next**: Ready for release/distribution.
