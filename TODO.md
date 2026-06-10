# AEO Audit CLI - Build Checklist

## Phase 1: Scaffold & Brain [x]

- [x] Create full directory structure
- [x] `pyproject.toml`: Hatch build, dependencies, entry points
- [x] `config.yaml`: Weights, thresholds, crawler settings
- [x] `cli.py`: Click command stubs (scan, batch, diff, config, monitor)
- [x] `claude.md`: Project context and architecture rules
- [x] `TODO.md`: This checklist
- [x] `__init__.py` files for all packages
- [x] `pytest` passes with 0 tests
- [x] Show project tree

## Phase 2: Integration Tests & Mock Site Verification [x]

- [x] Mock Server Setup
  - [x] Create `tests/fixtures/server.py` with dynamic, config-driven endpoint system
  - [x] Configure `tests/fixtures/mock_sites/perfect/` (static files + config.yaml)
  - [x] Configure `tests/fixtures/mock_sites/missing_manifest/` (static files + config.yaml)
  - [x] Configure `tests/fixtures/mock_sites/broken_mcp/` (static files + config.yaml)
  - [x] Configure `tests/fixtures/mock_sites/no_pricing/` (static files + config.yaml)
  - [x] Configure `tests/fixtures/mock_sites/no_trust/` (static files + config.yaml)
  - [x] Configure `tests/fixtures/mock_sites/minimal/` (static files + config.yaml)
- [x] Golden Master Scoring Fixture
  - [x] Configure `tests/fixtures/expected_scores.json` with expected grades, categories, and check results
- [x] Integration Fixture Wiring
  - [x] Update `tests/conftest.py` with mock server fixture, playwright/crawler, and test configs
- [x] Category-by-Category Test Suites
  - [x] Write `tests/integration/test_crawler.py` (verify crawler integration)

## Phase 3: Production Hardening & Polish [x]

- [x] Green Test Suite (Zero-Tolerance Policy)
  - [x] Correct all 26 checks to pass on perfect site and fail on target sites
  - [x] Validate scoring category math matches golden masters (+/- 0.5)
  - [x] Validate PDF output (>1KB, valid PDF format)
  - [x] Verify all subprocess CLI calls exit with status 0
- [x] Complete Reporters (aeo_audit/reporters/)
  - [x] HTML: CSS injection, Chart.js radar chart, collapsible findings, print media queries
  - [x] PDF: WeasyPrint compilation layer, page-break compliance, state score headers/footers, tagged structures
  - [x] Terminal: Rich data trees, summary tables, --verbose details dump
  - [x] JSON: Schema-validated payload, runtime profiling, cache engine metrics
- [x] CLI Polish (aeo_audit/cli.py)
  - [x] Complete scan command args: --user-agent, --headers, --concurrency, --no-cache, --timeout
  - [x] Complete batch command: newline-delimited/JSON arrays, --fail-fast, --progress
  - [x] Complete diff command: visual HTML delta blocks of site configurations
  - [x] Complete config subcommands: init, validate, show
  - [x] Complete monitor command: daemon mode, SQLite tracking, alerting webhooks, --alert-threshold
  - [x] Global CLI flags: --verbose, --quiet, --color
- [x] Caching & Performance Subsystems
  - [x] SQLite Cache: cryptographically secure key hash (url, method, headers, body)
  - [x] Concurrency Orchestration: Queue and asyncio.Semaphore pacing
  - [x] Network Resilience: Exponential backoff with random micro-jitter
  - [x] Logging: Latency, transfer weight, hit/miss statuses
- [x] Packaging & Distribution
  - [x] Hatch toolchain configurations (sdist, wheel)
  - [x] PyInstaller executable compilation build specification (hidden imports, assets)
  - [x] GitHub Actions workflow (.github/workflows/ci.yml)
  - [x] Homebrew Formula automated generation
  - [x] Host-specific installer script (get.aeo-audit.dev)
- [x] Complete Documentation Suite
  - [x] README.md: Badges, install, quick-start, configuration examples, layout structure
  - [x] Parameter config reference (bounds, fallback values)
  - [x] Custom plugin workspace extension guide
  - [x] CI/CD integration recipes
  - [x] Troubleshooting remediations (SSL, rate-limiting, edge-cases)

## Phase 4: Models [x]

- [x] `core/models.py`: Pydantic v2 strict models
  - [x] Category, Severity, CheckStatus, Grade enums
  - [x] Finding, CheckResult, CategoryScore models
  - [x] ConfidenceInterval, Scorecard, ScanResult models
  - [x] CheckContext, Config models
- [x] Unit tests for all models (`tests/unit/test_models.py`)
- [x] `mypy --strict` passes on models

## Phase 5: Crawler [x]

- [x] `core/crawler.py`: Playwright wrapper
  - [x] Browser context lifecycle (aenter/aexit)
  - [x] `fetch()`: Render JS, extract metadata
  - [x] `fetch_raw()`: Raw HTTP via httpx
  - [x] `mcp_handshake()`: JSON-RPC initialize
  - [x] `mcp_tools_list()`: Fetch tools
  - [x] `dns_lookup()`: TXT/SRV records via dnspython
- [x] `utils/http.py`: Retry, rate limiting
- [x] `utils/cache.py`: SQLite response cache
- [x] Unit tests for crawler (mocked Playwright)

## Phase 6: Check Registry [x]

- [x] `core/registry.py`: Plugin system
  - [x] Manual registration
  - [x] Built-in module discovery
  - [x] Entry point discovery
- [x] `checks/base.py`: AbstractBaseCheck
- [x] Contract tests: all checks implement BaseCheck

## Phase 7: Launch Readiness [~]

- [x] Scoring overhaul (make the score a usable feedback loop)
  - [x] Foundation-weighted category + check weights (Trust/Capabilities/Discovery lead)
  - [x] Percentile-relative overall grading (`benchmarks.grade_percentiles`)
  - [x] Robust benchmark path resolver (repo / installed / binary)
  - [x] Seed benchmark corpus via `scripts/gen_benchmark.py`
- [x] Correctness & reliability fixes
  - [x] `robots_agent`: self-fetch fallback (was never fed `robots_txt` in prod) + tiered scoring
  - [x] Crawl flakiness: `wait_strategy: load` (was `networkidle`), default timeout 30 -> 45
- [x] Install-path fixes (launch blocker)
  - [x] Repo-owner refs `ayushjangid` -> `AJ-EN` (README, pyproject, config UA, install.sh)
  - [x] `pipx install git+https://...` documented (PyPI marked "once published")
  - [x] Binary Chromium runtime documented (`PLAYWRIGHT_BROWSERS_PATH`)
  - [x] Fixed broken `file:///` doc links -> relative paths
- [x] Published to PyPI (v1.2.1, token auth; Trusted Publishing deferred post-launch)
- [x] Reports lead with absolute score + checks-passed; percentile labeled "of N sites" (v1.2.0)
- [x] Benchmark packaged inside the wheel (percentile grading was dead for installed users)
- [x] `--version` reads from dist metadata; zero-setup first run (auto-installs Chromium) (v1.2.1)
- [x] Launch assets: demo GIF, social card, badges, repo topics/homepage
- [x] GitHub Pages landing page live: https://aj-en.github.io/aeo-audit/

## Phase 8: Launch & Iterate [~]

- [x] Soft launch on X (@Ayush_observer) — thread posted
- [x] Hosted web demo built (`webdemo/`): FastAPI around `ScanEngine`, SSRF guard, rate limit, Dockerfile + fly.toml; verified end-to-end locally
- [x] Landing page hero now embeds the live scan widget (chips, scorecard, share button; graceful fallback when API is down)
- [ ] Deploy demo to Fly.io: `fly deploy -c webdemo/fly.toml` from repo root — **user task** (needs Fly account; first build is slow, bakes Chromium)
- [ ] r/LLMDevs post (use no-link-in-body trick; links in first comment)
- [ ] Recover HN account (emailed hn@ycombinator.com) -> then Show HN (one-shot, don't burn early)
- [ ] Write + send outreach emails: trigger.dev (Eric Allam), temporal.io (Maxim Fateev)
- [ ] Profile polish: bio (agentic-web builder, not "AEO Audit guy"), website->landing, pin launch
- [ ] Set up feedback capture (GitHub Discussions / issue template); iterate product on real input
- [ ] Configure PyPI Trusted Publishing (OIDC); delete `PYPI_API_TOKEN` secret

> NOTE for new sessions: `git push` fails from the agent env (`tls: bad record MAC`).
> Use `gh api` Contents REST API for pushes, or have the user run `git push`.
> Run everything via `.venv/bin/...`; set `PLAYWRIGHT_BROWSERS_PATH` for scans.
> See `claude.md` -> "Current State (Handoff)" for full context.

## Quality Gates

- [x] `mypy --strict aeo_audit/`: 0 errors (crawler, scoring, registry)
- [x] `ruff check aeo_audit/`: 0 errors
- [x] `ruff format --check aeo_audit/`: Clean
- [x] `pytest tests/unit -x -v`: 100% pass, >=80% coverage
- [x] `pytest tests/integration -x -v`: 100% pass (crawler integration)
- [x] `pytest tests/contract -x -v`: All interfaces honored
- [x] `aeo-audit scan https://httpbin.org --format json`: Valid JSON
