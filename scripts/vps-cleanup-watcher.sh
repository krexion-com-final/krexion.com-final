#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# Krexion — VPS Cleanup Watcher
# ─────────────────────────────────────────────────────────────────────
# Runs every minute via cron. Two responsibilities:
#
# 1. Write live host stats to /opt/krexion/data/host_stats.json so the
#    admin panel can display disk/memory/load (the backend container
#    cannot see host metrics directly).
#
# 2. If /opt/krexion/data/cleanup_requested.flag exists, run SAFE
#    cleanup actions and write the result to cleanup_result.json.
#
# ─────────────────────────────────────────────────────────────────────
# WHAT THIS SCRIPT NEVER TOUCHES
#   - Any Docker named volume (mongo data, uploaded resources,
#     RUT results, Caddy ACME certs)
#   - Active containers, running images
#   - Any file under /opt/krexion/ (your repo + backups)
#   - User data of any kind
#
# Safe cleanup actions only:
#   - docker builder prune -af   (build cache only)
#   - docker container prune -f  (already-stopped containers)
#   - docker image prune -f      (DANGLING images only, no -a flag)
#   - journalctl --vacuum-time=7d
#   - apt-get clean
#   - rotate Caddy access log if > 10 MB
#   - delete /tmp/playwright_*_profile-* directories older than 24h
# ─────────────────────────────────────────────────────────────────────

set -u
FLAG_DIR=/opt/krexion/data
FLAG_FILE="$FLAG_DIR/cleanup_requested.flag"
RESULT_FILE="$FLAG_DIR/cleanup_result.json"
STATS_FILE="$FLAG_DIR/host_stats.json"
LOG_FILE=/var/log/krexion-cleanup.log

mkdir -p "$FLAG_DIR"
touch "$LOG_FILE" 2>/dev/null || LOG_FILE=/tmp/krexion-cleanup.log

# ── Helper: write host stats JSON atomically ─────────────────────────
write_stats() {
  local disk_used disk_free_gb mem_pct swap_pct load updated
  disk_used=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
  disk_free_gb=$(df -BG / | tail -1 | awk '{print $4}' | tr -d 'G')
  mem_pct=$(free | awk '/^Mem:/ {if ($2 > 0) printf "%.1f", $3/$2 * 100; else print "0"}')
  swap_pct=$(free | awk '/^Swap:/ {if ($2 > 0) printf "%.1f", $3/$2 * 100; else print "0"}')
  load=$(awk '{print $1}' /proc/loadavg)
  updated=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  cat > "$STATS_FILE.tmp" <<EOF
{
  "disk_used_pct": $disk_used,
  "disk_free_gb": $disk_free_gb,
  "memory_used_pct": $mem_pct,
  "swap_used_pct": $swap_pct,
  "load_avg_1m": $load,
  "updated_at": "$updated"
}
EOF
  mv "$STATS_FILE.tmp" "$STATS_FILE"
  chmod 644 "$STATS_FILE" 2>/dev/null || true
}

# Always update stats (every minute)
write_stats

# ── Exit if no cleanup requested ─────────────────────────────────────
[ -f "$FLAG_FILE" ] || exit 0

echo "[$(date)] cleanup flag detected, starting…" >> "$LOG_FILE"

BEFORE_USED_KB=$(df / | tail -1 | awk '{print $3}')

# Helper: safely capture command output one-line for JSON
oneline() { tr '\n' ' ' | sed 's/"/\\"/g' | head -c 500; }

# 1. Docker build cache prune (biggest win, totally safe)
DOCKER_BUILDER=$(docker builder prune -af 2>&1 | tail -2 | oneline)

# 2. Stopped containers (none are deleted while running)
DOCKER_CONTAINERS=$(docker container prune -f 2>&1 | tail -1 | oneline)

# 3. Dangling images only (no -a flag — used images stay)
DOCKER_IMAGES=$(docker image prune -f 2>&1 | tail -1 | oneline)

# 4. System journal logs older than 7 days
JOURNAL=$(journalctl --vacuum-time=7d 2>&1 | tail -2 | oneline)

# 5. APT package cache
apt-get clean >/dev/null 2>&1 && APT="apt cache cleaned" || APT="apt clean skipped"

# 5b. 2026-06 — clear OS thumbnail / unattended-upgrade leftover caches
# (safe, gets regenerated on demand). Adds another ~50-200 MB of headroom
# on long-running VPS hosts.
EXTRA_CACHE=""
if [ -d /var/cache/man ]; then
  rm -rf /var/cache/man/* 2>/dev/null || true
  EXTRA_CACHE="${EXTRA_CACHE} man-cache"
fi
if [ -d /var/cache/debconf ]; then
  find /var/cache/debconf -name "*-old" -mtime +7 -delete 2>/dev/null || true
  EXTRA_CACHE="${EXTRA_CACHE} debconf-old"
fi
if [ -d /root/.cache ]; then
  # Skip ~/.cache/playwright (browser binaries; reinstalling them is 300+ MB)
  find /root/.cache -mindepth 1 -maxdepth 1 ! -name playwright -exec rm -rf {} + 2>/dev/null || true
  EXTRA_CACHE="${EXTRA_CACHE} root-cache"
fi
[ -z "$EXTRA_CACHE" ] && EXTRA_CACHE="none"

# 6. Caddy access log rotation (if larger than 10 MB)
CADDY_LOG=/var/lib/docker/volumes/krexion_caddy_data/_data/access.log
CADDY_OUT="caddy log not present"
if [ -f "$CADDY_LOG" ]; then
  CADDY_SIZE=$(stat -c%s "$CADDY_LOG" 2>/dev/null || echo 0)
  if [ "$CADDY_SIZE" -gt 10485760 ]; then
    TS=$(date +%Y%m%d-%H%M%S)
    gzip -c "$CADDY_LOG" > "${CADDY_LOG%.log}-${TS}.log.gz" 2>/dev/null && \
      : > "$CADDY_LOG" && \
      CADDY_OUT="caddy log rotated and compressed (${CADDY_SIZE} bytes)" || \
      CADDY_OUT="caddy log rotate failed"
  else
    CADDY_OUT="caddy log small ($CADDY_SIZE bytes) — no rotation needed"
  fi
fi

# 7. Stale /tmp/playwright_* profiles older than 1 day
TMP_COUNT=0
if compgen -G "/tmp/playwright_*" >/dev/null; then
  TMP_COUNT=$(find /tmp -maxdepth 1 -name "playwright_*" -type d -mtime +1 2>/dev/null | wc -l)
  find /tmp -maxdepth 1 -name "playwright_*" -type d -mtime +1 -exec rm -rf {} + 2>/dev/null || true
fi
TMP_OUT="${TMP_COUNT} stale playwright temp dirs removed"

AFTER_USED_KB=$(df / | tail -1 | awk '{print $3}')
FREED_KB=$((BEFORE_USED_KB - AFTER_USED_KB))
FREED_MB=$((FREED_KB / 1024))
[ "$FREED_MB" -lt 0 ] && FREED_MB=0

cat > "$RESULT_FILE.tmp" <<EOF
{
  "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "freed_mb": $FREED_MB,
  "before_used_kb": $BEFORE_USED_KB,
  "after_used_kb": $AFTER_USED_KB,
  "actions": {
    "docker_builder_prune": "$DOCKER_BUILDER",
    "docker_container_prune": "$DOCKER_CONTAINERS",
    "docker_image_prune_dangling": "$DOCKER_IMAGES",
    "journalctl_vacuum": "$JOURNAL",
    "apt_clean": "$APT",
    "extra_cache_cleanup": "$EXTRA_CACHE",
    "caddy_log_rotate": "$CADDY_OUT",
    "tmp_playwright_cleanup": "$TMP_OUT"
  }
}
EOF
mv "$RESULT_FILE.tmp" "$RESULT_FILE"
chmod 644 "$RESULT_FILE" 2>/dev/null || true

# Clear the flag so we don't run again
rm -f "$FLAG_FILE"

# Refresh stats after cleanup
write_stats

echo "[$(date)] cleanup complete, freed ${FREED_MB} MB" >> "$LOG_FILE"
