# Build from the REPO ROOT so the demo runs the exact code in this repo:
#   docker build -f webdemo/Dockerfile -t aeo-demo .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install the package + web deps first (better layer caching).
COPY pyproject.toml README.md /app/
COPY aeo_audit /app/aeo_audit
COPY webdemo/requirements.txt /app/webdemo/requirements.txt
RUN pip install . -r webdemo/requirements.txt

# Pull Chromium + its OS deps into the image so first scan is instant.
RUN playwright install --with-deps chromium

# App code last — cheap layer to rebuild.
COPY webdemo /app/webdemo

EXPOSE 8080
CMD ["sh", "-c", "uvicorn webdemo.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
