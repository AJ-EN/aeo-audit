# Changelog

All notable changes to `aeo-audit` are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-06-10

### Changed
- CI: bumped GitHub Actions to their Node 24 majors (`checkout@v6`,
  `setup-python@v6`, `upload-artifact@v7`, `download-artifact@v8`).
- Refreshed the benchmark corpus under the fixed scoring so percentile grades
  rank sites against a field measured the same way.

### Added
- First release published to PyPI (`pip install aeo-audit`).

## [1.1.0] - 2026-06-09

Launch-readiness release: makes the score a usable feedback loop and fixes
reliability and install blockers.

### Changed
- **Foundation-weighted scoring.** Category and per-check weights now favour the
  signals well-run APIs already expose today (Trust, Capabilities, Discovery)
  so the score differentiates real sites instead of collapsing every site to F.
- **Percentile-relative overall grading.** Grades rank a site against a
  benchmark corpus (A = top 10%), with absolute-threshold fallback when no
  corpus is loaded. Category grades remain absolute.
- **Crawler wait strategy is now `load`** (was `networkidle`, which never
  settles on long-polling sites); default timeout raised 30s → 45s. Both are
  config-driven.

### Fixed
- **`robots_agent` always failed in production.** The crawler never populated
  `context.robots_txt`, so the check scored 0 for every site. Added a self-fetch
  fallback and tiered scoring (explicit allow / allow-all / blocked / missing).
- **Install paths.** Corrected repository-owner references, documented
  `pipx install git+https://…` and the standalone binary's Chromium runtime
  requirement, and fixed broken documentation links.

### Added
- `scripts/gen_benchmark.py` to (re)generate the percentile benchmark corpus
  from a results file under the current weights.
- Robust benchmark-path resolution that works from the repo, an installed
  package, and the bundled binary.

## [1.0.0] - 2026-06-07

- Initial release: 26 checks across 5 dimensions, 4 reporters (terminal, HTML,
  PDF, JSON), SQLite cache, CLI (scan, batch, diff, config, monitor), and
  Hatch / PyInstaller / Homebrew packaging.
