#!/usr/bin/env bash
# RealFlow -- Hardware Detection & Performance Profile Picker (Linux/macOS)
#
# Outputs env-style key=value lines on stdout. Usage:
#   eval "$(./scripts/detect-hardware.sh)"
#   echo "Tier: $RF_TIER, RUT concurrency: $RF_RUT_CONCURRENCY"
#
# Tiers (same as Windows):
#   MICRO  -- RAM <= 6 GB                  -- 1 RUT worker
#   LOW    -- RAM 7-10 GB                  -- 2 RUT workers
#   MID    -- RAM 11-16 GB                 -- 4 RUT workers
#   HIGH   -- RAM 17-32 GB                 -- 8 RUT workers
#   BEAST  -- RAM > 32  GB                 -- 16 RUT workers
#
# CPU cores act as a HARD ceiling: actual = min(tier, cores*2)

set -e

# --- detect RAM ---
if [[ "$OSTYPE" == "darwin"* ]]; then
    RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
    RAM_GB=$(( RAM_BYTES / 1024 / 1024 / 1024 ))
    CPU_CORES=$(sysctl -n hw.logicalcpu 2>/dev/null || echo 2)
else
    RAM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
    RAM_GB=$(( RAM_KB / 1024 / 1024 ))
    CPU_CORES=$(nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo 2>/dev/null || echo 2)
fi

# --- detect free disk on / ---
FREE_DISK_GB=$(df -BG / 2>/dev/null | awk 'NR==2 {gsub("G",""); print $4}' || echo 0)
FREE_DISK_GB=${FREE_DISK_GB:-0}

# --- pick tier ---
if   [ "$RAM_GB" -le 6  ]; then  TIER="MICRO"; RUT=1;  MONGO_CAP="512m";  BE_CAP="1536m"; FE_CAP="128m"; WSL_MEM="4GB"
elif [ "$RAM_GB" -le 10 ]; then  TIER="LOW";   RUT=2;  MONGO_CAP="1g";    BE_CAP="2560m"; FE_CAP="192m"; WSL_MEM="5GB"
elif [ "$RAM_GB" -le 16 ]; then  TIER="MID";   RUT=4;  MONGO_CAP="2g";    BE_CAP="4g";    FE_CAP="256m"; WSL_MEM="10GB"
elif [ "$RAM_GB" -le 32 ]; then  TIER="HIGH";  RUT=8;  MONGO_CAP="4g";    BE_CAP="8g";    FE_CAP="384m"; WSL_MEM="20GB"
else                             TIER="BEAST"; RUT=16; MONGO_CAP="8g";    BE_CAP="16g";   FE_CAP="512m"; WSL_MEM="32GB"
fi

# --- CPU ceiling ---
CPU_CEILING=$(( CPU_CORES * 2 ))
[ "$CPU_CEILING" -lt 1 ] && CPU_CEILING=1
[ "$RUT" -gt "$CPU_CEILING" ] && RUT=$CPU_CEILING

# --- pick compose override ---
case "$TIER" in
    MICRO) COMPOSE_FILE="docker-compose.micro.yml"  ;;
    LOW)   COMPOSE_FILE="docker-compose.lowram.yml" ;;
    MID)   COMPOSE_FILE="docker-compose.mid.yml"    ;;
    HIGH)  COMPOSE_FILE="docker-compose.high.yml"   ;;
    BEAST) COMPOSE_FILE="docker-compose.beast.yml"  ;;
esac

# If user passed --human, print a friendly summary instead of env vars
if [ "${1:-}" = "--human" ]; then
    echo ""
    echo "  ===== RealFlow Hardware Profile ====="
    echo "  RAM total          : ${RAM_GB} GB"
    echo "  CPU logical cores  : ${CPU_CORES}"
    echo "  Root free space    : ${FREE_DISK_GB} GB"
    echo ""
    echo "  >>> Selected tier  : ${TIER}"
    echo ""
    echo "  RUT concurrency    : ${RUT} parallel browsers"
    echo "  Mongo memory cap   : ${MONGO_CAP}"
    echo "  Backend memory cap : ${BE_CAP}"
    echo "  Frontend cap       : ${FE_CAP}"
    echo "  WSL memory (Win)   : ${WSL_MEM}"
    echo "  Compose override   : ${COMPOSE_FILE}"
    echo ""
    exit 0
fi

# Default: emit env-style for `eval`
cat <<EOF
export RF_TIER="$TIER"
export RF_RAM_GB="$RAM_GB"
export RF_CPU_CORES="$CPU_CORES"
export RF_FREE_DISK_GB="$FREE_DISK_GB"
export RF_RUT_CONCURRENCY="$RUT"
export RF_MONGO_CAP="$MONGO_CAP"
export RF_BACKEND_CAP="$BE_CAP"
export RF_FRONTEND_CAP="$FE_CAP"
export RF_WSL_MEMORY="$WSL_MEM"
export RF_COMPOSE_OVERRIDE="$COMPOSE_FILE"
EOF
