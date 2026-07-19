# syntax=docker/dockerfile:1

# Scraper service: dashboard + crawl worker in one process. Deployed as a
# second service next to the backend, sharing its Postgres (build context is
# the scraper/ directory, e.g. Railway "Root Directory" = scraper).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS scraper
WORKDIR /app/scraper

# PYTHONUNBUFFERED: the worker logs via print(); without it nothing reaches
# the platform's log stream until the buffer flushes.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/scraper/.venv/bin:$PATH"

# Install Python dependencies first for layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Scraper source.
COPY . ./

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/healthcheck').status==200 else 1)"
CMD ["python", "main.py"]
