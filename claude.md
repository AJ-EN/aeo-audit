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
2. Category score = weighted average of check scores (per-check weights in `config.yaml`)
3. Overall = weighted average of 5 category scores (0-100)
4. Percentile rank against the benchmark corpus (`benchmarks/percentiles_v1.json`)
5. Bootstrap 1000 samples -> 95% CI
6. **Overall grade = percentile-relative**: A=top 10%, B=top 30%, C=top 60%, D=top 85%, F=bottom 15% (`benchmarks.grade_percentiles`). Falls back to absolute thresholds (A>=90...) when no corpus is loaded. **Category grades remain absolute.**

Rationale: agent-native standards are nascent, so every site's *absolute* score is low. Relative grading keeps the score a meaningful, movable target and the bar rises as the corpus improves. Regenerate the corpus with `scripts/gen_benchmark.py results.jsonl`.

## Category Weights (foundation-weighted)

Dimensions where well-run APIs already differ (Trust, Capabilities, Discovery) carry the most weight; emerging agent-native dimensions contribute upside without dominating.

| Category    | Weight |
|-------------|--------|
| Discovery   | 0.25   |
| Capabilities| 0.25   |
| Trust       | 0.25   |
| Commerce    | 0.15   |
| Identity    | 0.10   |

## Design Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-07 | Hatch over Poetry | Lighter, PEP 621 native, faster builds |
| 2026-06-07 | Pydantic v2 strict mode | Runtime validation + mypy compatibility |
| 2026-06-07 | SQLite for cache | Zero-dependency, single-file, fast reads |
| 2026-06-07 | httpx over aiohttp | Better typing, HTTP/2 support, simpler API |
| 2026-06-07 | Mock Server Setup | Config-driven standard library HTTP server for integration testing |
| 2026-06-07 | Phase 3 Hardening | Secure CLI, asynchronous reporters, robust caching, packaging, docs |
| 2026-06-09 | Foundation-weighted scoring | Identity+Commerce signals are ~0 across all real sites; reweighting toward Trust/Capabilities/Discovery gives a usable spread instead of a flat wall of F |
| 2026-06-09 | Percentile-relative grading | Absolute grades make every real site an F (standards are nascent); relative grades keep the score a movable target and the bar rises with the corpus |
| 2026-06-09 | `robots_agent` self-fetch + tiered | Crawler never populated `context.robots_txt` (check always failed in prod); added self-fetch fallback and tiered scoring (explicit allow / allow-all / blocked) |
| 2026-06-09 | `wait_strategy: load` | `networkidle` never settles on long-polling sites, causing spurious timeouts and score swings; `load` + `__AEO_READY__` is faster and deterministic |

## Current State

- **Phase**: 4 - Launch Readiness (In Progress)
- **Completed (Phase 1-3)**: All 26 checks, 4 reporters (HTML, PDF, Rich Terminal, JSON), SQLite cache, CLI subcommands (scan, batch, diff, config, monitor), Homebrew/installer/Hatch/PyInstaller packaging.
- **Completed (Phase 4)**: Scoring overhaul (foundation weights + percentile grading + seeded benchmark), `robots_agent` production-bug fix, crawl-flakiness fix, install-path fixes (repo owner refs, pipx-from-git, binary browser docs).
- **Next**: Publish to PyPI; host the `perfect/` mock as a live 100/100 demo; build launch assets (GitHub polish, demo GIF/video) sequenced GitHub -> Twitter -> Show HN -> Product Hunt.
