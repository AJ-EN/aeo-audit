# Dockerfile for the Hugging Face Space deployment.
# HF runs containers as UID 1000 and routes traffic to app_port (7860).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Match the UID Hugging Face runs the container as.
RUN useradd -m -u 1000 user

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Bake Chromium + OS deps into the image; world-readable so UID 1000 can run it.
RUN playwright install --with-deps chromium && chmod -R a+rX /ms-playwright

COPY app.py /app/app.py
COPY static /app/static

# The engine writes its SQLite cache to the working directory.
RUN chown -R user:user /app
USER user
ENV HOME=/home/user

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
