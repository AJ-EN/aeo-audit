# AEO Audit — hosted demo

A zero-install on-ramp to the CLI: paste a URL, get a live scorecard in ~30s.
It's a thin [FastAPI](https://fastapi.tiangolo.com/) wrapper around the same
`ScanEngine` the CLI runs, so the demo can never disagree with `aeo-audit scan`.

**Live deployment**: Hugging Face Space at
<https://huggingface.co/spaces/ayushjangid/aeo-audit-demo>
(app URL: `https://ayushjangid-aeo-audit-demo.hf.space`) — the landing page's
scan widget calls it cross-origin.

```
webdemo/
├── app.py            # FastAPI app: /api/scan + static hosting
├── static/index.html # the single-page frontend (matches the landing page)
├── requirements.txt  # fastapi + uvicorn (the engine comes from the parent pkg)
├── Dockerfile        # python:3.12-slim + Chromium, built from the REPO ROOT
├── fly.toml          # Fly.io deploy config (alternative, paid)
├── hf/               # Hugging Face Space variant (Dockerfile, README, reqs)
└── deploy_hf.py      # one-command deploy to the HF Space
```

## Safety rails (it's a public endpoint)

- **SSRF guard** — only `http(s)`; the host is DNS-resolved and any private,
  loopback, link-local, reserved, or multicast address is rejected (blocks
  cloud metadata + internal services).
- **Rate limit** — per-IP token bucket, default **5 scans/hour** (in-memory).
- **Concurrency cap** — a global semaphore limits simultaneous scans (default 2)
  so one small box can't be stampeded.

All three are env-tunable: `AEO_DEMO_RATE_PER_HOUR`, `AEO_DEMO_CONCURRENCY`,
`AEO_DEMO_SCAN_TIMEOUT`.

> The SSRF check validates the **submitted** host. A site that 3xx-redirects to
> an internal address inside the headless browser is a residual risk; the rate
> limit + concurrency cap keep blast radius small. Harden before high-traffic use.

## Run locally

From the repo root, with the project installed in your venv:

```bash
pip install -r webdemo/requirements.txt
export PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright"  # macOS
uvicorn webdemo.app:app --reload --port 8080
```

Open <http://localhost:8080>.

## Deploy to Hugging Face Spaces (free, no card — this is what's live)

The Space installs the released `aeo-audit` from PyPI and runs the wrapper in
`webdemo/` on a free 2 vCPU / 16GB machine. HF runs containers as UID 1000 on
port 7860 — `webdemo/hf/Dockerfile` handles both.

```bash
pip install huggingface_hub
HF_TOKEN=hf_xxx python webdemo/deploy_hf.py   # token: hf.co/settings/tokens (Write)
```

The free tier sleeps after ~48h without traffic; the first request after that
takes ~30–60s while the Space wakes. New engine release? Bump the pin in
`webdemo/hf/requirements.txt` and redeploy.

## Deploy to Fly.io (alternative, needs a card)

One-time:

```bash
brew install flyctl      # or: curl -L https://fly.io/install.sh | sh
fly auth login
fly launch --copy-config --no-deploy -c webdemo/fly.toml   # creates the app
```

Then, from the **repo root** (the Docker build context must be the root):

```bash
fly deploy -c webdemo/fly.toml
```

The first build is slow (it bakes Chromium into the image); subsequent deploys
reuse the layer. `auto_stop_machines` scales the machine to zero when idle, so
an unused demo costs roughly nothing.

### Memory
Chromium is memory-hungry. `fly.toml` starts at **1GB**; if you see OOM kills in
`fly logs`, bump `[[vm]].memory` to `2048`.

## Other hosts
Any container host works (Railway, Render, a VPS). Build the image from the repo
root and run it:

```bash
docker build -f webdemo/Dockerfile -t aeo-demo .
docker run -p 8080:8080 aeo-demo
```

## Wiring it to the landing page
Point the GitHub Pages "Scan your own" CTA at the deployed URL, or embed the
form there with `fetch()` calls to `https://<your-demo>/api/scan`.
