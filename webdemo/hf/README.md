---
title: AEO Audit — Live Scan Demo
emoji: 🛰️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Scan any site's AI-agent readiness (0-100), no install.
---

# AEO Audit — Live Scan Demo

Paste a URL, get a 0–100 **Agent/Engine Optimization** scorecard in ~30s —
Discovery, Identity, Capabilities, Commerce & Trust. This Space wraps the exact
same `ScanEngine` as the open-source CLI, so it can never disagree with
`aeo-audit scan`.

- **CLI / source**: https://github.com/AJ-EN/aeo-audit
- **Leaderboard & methodology**: https://aj-en.github.io/aeo-audit/
- **Install**: `pipx install aeo-audit` (unlimited local scans)

Public-endpoint safety rails: SSRF guard (rejects private/internal targets),
per-IP rate limit (5 scans/hour), global concurrency cap.
