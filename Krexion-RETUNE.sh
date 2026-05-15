#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
#  Krexion — RE-TUNE for current hardware (Linux/macOS)
#
#  Re-detects your PC's RAM + CPU cores, picks the optimal
#  performance tier and restarts the Krexion stack with the new
#  docker-compose override.
# ──────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo
echo "============================================================"
echo "   Krexion Hardware Re-Tune"
echo "============================================================"
echo

# Need sudo for docker on some distros
if [ "$(id -u)" -ne 0 ]; then
    exec sudo -E bash "$0" "$@"
fi

# 1. Detect
if [ ! -x ./scripts/detect-hardware.sh ]; then
    chmod +x ./scripts/detect-hardware.sh 2>/dev/null || true
fi

echo -e "${YELLOW}Step 1 / 3 -- Detecting hardware...${NC}"
./scripts/detect-hardware.sh --human
eval "$(./scripts/detect-hardware.sh)"

# 2. Restart with new override
echo
echo -e "${YELLOW}Step 2 / 3 -- Stopping current stack...${NC}"
COMPOSE_FILES="-f docker-compose.yml"
if [ -n "$RF_COMPOSE_OVERRIDE" ] && [ -f "$RF_COMPOSE_OVERRIDE" ]; then
    COMPOSE_FILES="$COMPOSE_FILES -f $RF_COMPOSE_OVERRIDE"
fi
docker compose $COMPOSE_FILES down || true

echo
echo -e "${YELLOW}Step 3 / 3 -- Starting with tier ${RF_TIER}...${NC}"
docker compose $COMPOSE_FILES up -d

echo
echo "============================================================"
echo -e "${GREEN}   Re-tune complete.${NC}"
echo "   Open http://localhost:3000 once Docker reports healthy."
echo "============================================================"
echo
