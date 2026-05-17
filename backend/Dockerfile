# ===============================================================
#   TrackMaster - Backend Dockerfile
#
#   Uses Microsoft's official Playwright Python image which already
#   has Chromium + all system dependencies pre-installed, so the
#   build is fast and reliable.
# ===============================================================
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install curl for healthchecks (everything else already there)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Python deps (cached layer) ----
# Main requirements (public PyPI only — never fails)
COPY requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && grep -v "^emergentintegrations" requirements.txt > /tmp/req-core.txt \
    && pip install -r /tmp/req-core.txt

# Optional: emergentintegrations from Emergent's private CDN
# (used only by AI automation generator — wrapped in try/except in code,
# so build will NOT fail if CDN is unreachable)
RUN pip install emergentintegrations==0.1.0 \
        --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ \
        || echo "WARN: emergentintegrations install skipped (AI features will gracefully degrade)"

# ---- Copy source + compile to bytecode for shipping ----
# We copy the .py files only for the build stage, compile them into
# optimised .pyc bytecode, then DELETE the originals. Customers who
# inspect /app inside the container will only see compiled artefacts —
# no readable Python source. This is not unbreakable encryption
# (anyone with disassembly tools can reverse .pyc) but raises the bar
# significantly against casual tampering / "free copying" by technical
# customers and stops accidental edits.
COPY . .

# Compile every .py recursively to optimised .pyc and remove source.
# The PYTHONDONTWRITEBYTECODE=1 above is overridden during this step
# because we explicitly run compileall.
RUN python -O -m compileall -b -f -q . \
    && find . -name "*.py" -type f -not -path "./tests/*" -delete \
    && find . -name "__pycache__" -type d -prune -exec rm -rf {} + \
    && find . -name "*.pyc" -type f | head -20

EXPOSE 8001

# Multi-worker uvicorn for higher concurrency under bulk RUT/CPI load.
# ────────────────────────────────────────────────────────────────────
# 2026-01 IMPORTANT — DEFAULT REVERTED FROM 4 → 1 WORKER
# ────────────────────────────────────────────────────────────────────
# Krexion's RUT engine keeps **per-job state in process memory**
# (`RUT_JOBS[job_id]` dict, asyncio.Event objects, ws clients, the
# memory-pressure throttle counter, etc.) — none of it is serialised
# to Mongo, only the periodic _persist() snapshot is.
#
# With 4 workers:
#  • A job created on worker-A only has its in-memory state on
#    worker-A. UI polls / cancel requests round-robin to workers
#    B/C/D return stale or empty state.
#  • A Playwright OOM in worker-A crashes ONLY worker-A — uvicorn
#    silently respawns it, the new worker's startup reaper sees
#    the orphan job in Mongo, bumps `restart_count`, kicks off
#    auto-resume. From the user's POV the job appears to "restart
#    itself" out of nowhere — exactly the bug reported in
#    Jan 2026 ("preparing pe wapas chala jata hai").
#  • 4 × Playwright browser pools × ~1.5 GB each = 6 GB instantly,
#    overwhelming the 6 GB container cap → cgroup OOM-kill → full
#    container restart cycle.
#
# Switching to **single-worker** fixes ALL of the above:
#  • Process memory is the single source of truth — no fragmented
#    RUT_JOBS state across processes.
#  • A worker crash IS a container crash → Docker's restart
#    policy kicks in cleanly, reaper runs ONCE, auto-resume is
#    deterministic.
#  • All 6 GB available to the single Playwright pool — far more
#    headroom for high-concurrency RUT runs (10-20 browsers).
#  • asyncio + uvloop in one process easily handles thousands of
#    concurrent HTTP requests for an admin panel like Krexion
#    (typical traffic is <50 RPS, miles below uvicorn's per-worker
#    limit of 10k+ RPS).
#
# Owners running >100 RPS sustained CRUD traffic can override via
# `UVICORN_WORKERS=2` env-var — but ONLY if no big RUT jobs are
# expected; multi-worker breaks long-running BG-task semantics.
ENV UVICORN_WORKERS=1
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8001} --workers ${UVICORN_WORKERS:-1} --loop uvloop --http httptools --backlog 4096 --limit-concurrency 1000 --timeout-keep-alive 75 --proxy-headers --forwarded-allow-ips '*'"]
