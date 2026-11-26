# syntax=docker/dockerfile:1
#
# Cobalt Sequence Lab image: runs `cobalt-server` by default; the CLI runs when given as the
# command (`docker run IMAGE cobalt stats file.fasta`). See "Running in Docker" in README.md.

# --- build: install the package and its server dependencies into a venv ---
FROM python:3.12-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
# Add `rna` to the extras once /foldrna is implemented: ".[server,rna]"
RUN pip install ".[server]"

# --- runtime: the venv only, no build context or pip cache ---
FROM python:3.12-slim

ARG VERSION=dev
LABEL org.opencontainers.image.title="Cobalt Sequence Lab" \
      org.opencontainers.image.description="Biopython sequence processing CLI and HTTP server" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COBALT_LOG_FORMAT=plain \
    COBALT_SERVER_HOME=/data/.cobalt-server

COPY --from=build /opt/venv /opt/venv

# /data is owned by cobalt: the server creates its config and storage in $COBALT_SERVER_HOME
# (/data/.cobalt-server). Admin commands find it from any cwd:
#   docker exec -it CONTAINER cobalt-admin users add ada
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin cobalt \
    && mkdir -p /data && chown cobalt:cobalt /data
USER cobalt

# Bind-mount input files here for CLI use: docker run -v "$PWD:/data" IMAGE cobalt stats x.fasta
# For the server, mount a volume here to keep .cobalt-server (config and storage)
WORKDIR /data

EXPOSE 8000

# GET /api/health is public (no API key needed); slim images have no curl
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"]

# Exec form: cobalt-server is PID 1 and gets SIGTERM directly, so uvicorn shuts down gracefully.
# COBALT_API_KEYS (comma-separated) must be provided at runtime; it is never baked into the image.
CMD ["cobalt-server", "--host", "0.0.0.0", "--port", "8000", "--auth", "api-key"]
