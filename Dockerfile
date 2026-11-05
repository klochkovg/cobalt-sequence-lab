# syntax=docker/dockerfile:1
#
# Cobalt Sequence Lab image: runs `cobalt serve` by default, and any other `cobalt` command when
# one is given (`docker run IMAGE stats file.fasta`). See "Running in Docker" in README.md.

# --- build: install the package and its serve dependencies into a venv ---
FROM python:3.12-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
# Add `rna` to the extras once /foldrna is implemented: ".[serve,rna]"
RUN pip install ".[serve]"

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
    COBALT_LOG_FORMAT=plain

COPY --from=build /opt/venv /opt/venv

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin cobalt
USER cobalt

# Bind-mount input files here for CLI use: docker run -v "$PWD:/data" IMAGE stats x.fasta
WORKDIR /data

EXPOSE 8000

# GET / is public (no API key needed) and returns the version; slim images have no curl
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=2)"]

# Exec form: cobalt is PID 1 and gets SIGTERM directly, so uvicorn shuts down gracefully.
# COBALT_API_KEYS (comma-separated) must be provided at runtime; it is never baked into the image.
ENTRYPOINT ["cobalt"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000", "--auth", "api-key"]
