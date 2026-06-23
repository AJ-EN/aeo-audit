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
| 2026-06-10 | Reports lead with absolute truth | A site passing 6/26 checks showing a green "A" overstated; reports now lead with `score/100` + `passes X/Y checks`, label percentile as "rank of N benchmarked sites", and show a fix-list. Added `Scorecard.benchmark_size` |
| 2026-06-10 | Benchmark shipped inside the wheel | Corpus lived at repo-root `benchmarks/` (outside `packages=["aeo_audit"]`), so pip-installed users silently got absolute grading (all F). Moved to `aeo_audit/benchmarks/`; updated `gen_benchmark.py` + `aeo_audit.spec` |
| 2026-06-10 | `__version__` from dist metadata | Was hardcoded `1.0.0` in `__init__.py` and drifted; now `importlib.metadata.version("aeo-audit")` (single source of truth) |
| 2026-06-10 | Auto-install Chromium on first run | `pip install` doesn't pull the browser; first scan crashed. Crawler now detects the missing browser, runs `playwright install chromium` once, and retries |
| 2026-06-10 | Token publish (Trusted Publishing deferred) | Switched PyPI publish to OIDC, then reverted to `PYPI_API_TOKEN` so the urgent v1.1.2 release could ship before configuring a Trusted Publisher on PyPI (post-launch TODO) |

## Current State (Handoff — last updated 2026-06-11)

**Phase 5 — Launched & iterating.** The product is built, shipped, and live; focus is now feedback + build-led iteration, not more building of core features.

### Shipped / live
- **PyPI**: `aeo-audit` **v1.2.1** live — `pip install aeo-audit` / `pipx install aeo-audit`. Verified working from a clean machine (browser auto-installs on first scan).
- **GitHub**: `https://github.com/AJ-EN/aeo-audit` (owner is **AJ-EN**, not ayushjangid). Repo polished: badges, topics, homepage, demo GIF, CHANGELOG. Releases v1.0.0–v1.2.1 with Linux+macOS binaries attached.
- **Landing page (GitHub Pages)**: `https://aj-en.github.io/aeo-audit/` — hero now leads with a **live "scan your site" widget** (example chips, animated scorecard, share-on-X button), plus demo GIF, the 19-site leaderboard, methodology, example report, social-preview card (`docs/assets/og-card.jpg`) + favicon. Served from `main` `/docs`.
- **Hosted web demo** (`webdemo/`, 2026-06-11): FastAPI wrapper around `ScanEngine` (SSRF guard, 5 scans/hr/IP, concurrency cap 2, CORS locked to `aj-en.github.io`). **Deployed as a free Hugging Face Space** under the user's HF account `ayushjangid` (Fly.io abandoned — user has no card money; HF free tier: 2 vCPU/16GB, no card). Space: `https://huggingface.co/spaces/ayushjangid/aeo-audit-demo`, app URL `https://ayushjangid-aeo-audit-demo.hf.space` (= `DEMO_API` in `docs/index.html`). Redeploy: `HF_TOKEN=… .venv/bin/python webdemo/deploy_hf.py` (installs `aeo-audit` from PyPI — bump the pin in `webdemo/hf/requirements.txt` on engine releases). Free tier sleeps after ~48h idle; first request then takes ~30–60s (widget's loading steps cover it).
- All 26 checks, 4 reporters, CLI (scan/batch/diff/config/monitor), 206 tests passing, `mypy --strict` + `ruff` clean, coverage ~80%.

### Launch status (soft launch done 2026-06-10)
- **X**: launch thread posted from **@Ayush_observer** (12 followers — small account). Live.
- **Reddit**: r/SideProject post was auto-removed by spam filter (low karma). r/LLMDevs not yet posted — must use the **no-link-in-body trick** (links go in the first comment) to survive the filter.
- **Hacker News**: account `__ayush__` (since 2021, double underscores both sides — earlier "locked" was just a username typo, never actually locked). Low-karma/dormant. **Show HN posted 2026-06-13 (Tue ~6:15pm IST) and auto-flagged within ~1 min** — classic low-karma-account-drops-self-promo-link filter, not a content judgment. Emailed hn@ycombinator.com to request unflag / second-chance pool. Next time: build karma first (thoughtful comments) before submitting links.
- **Outreach emails** to trigger.dev (Eric Allam) / temporal.io (Maxim Fateev): drafted-in-conversation but **not yet written/sent**. Highest-value remaining channel (no gatekeeper).

### CRITICAL gotchas for a new session (saves re-deriving)
- **`git push` FAILS from the agent environment** (`tls: bad record MAC` — corrupts on anything but tiny payloads). Workaround that works: **GitHub Contents REST API** (`gh api -X PUT repos/AJ-EN/aeo-audit/contents/<path>` with base64 content), or have the **user run `git push`** from their own terminal. `gh api` works fine; only git's pack-transfer fails.
- **Always run via the venv**: `.venv/bin/aeo-audit`, `.venv/bin/python -m pytest`. For any scan, set `PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright"`.
- **Honest-grading principle (do NOT regress)**: score is absolute truth; grade is a *relative rank* and must always be labeled "of N sites". Never inflate a low-score site to a bare "A".
- Full corpus re-scan → `aeo-audit batch targets.txt --format jsonl -o results.jsonl` then `python scripts/gen_benchmark.py results.jsonl`. `results.jsonl` is **gitignored** (scraped pages can contain secrets — GitHub push-protection once caught a Replicate token in it).

### Strategy aligned with the user (don't relitigate)
- Build > distribute (~80/20). Don't game follower metrics. The signal that matters: **does anyone scan/star/give real feedback** — driven by a better product, not more posts.
- Position the user as **a builder in the agentic-web space**, not "the AEO Audit guy" — AEO Audit is chapter one. Bio: `Building open-source tools for the agentic web. Currently: aeo-audit, a scanner for AI-agent readiness.`

### Next steps
1. Profile polish (bio/website/pin) — user task.
3. Draft + send the two outreach emails (now stronger: include the "scan yourself in the browser" link).
4. Show HN when the account is recovered.
5. Set up feedback capture (GitHub Discussions / issue template) and iterate the product on real input.
6. Post-launch: configure PyPI Trusted Publishing, delete `PYPI_API_TOKEN`.
