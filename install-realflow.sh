#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                  ║
# ║         REALFLOW — ONE-CLICK INSTALLER (Linux / macOS)           ║
# ║                                                                  ║
# ║  Run on any fresh Ubuntu/Debian/Fedora/macOS machine:            ║
# ║                                                                  ║
# ║    curl -fsSL https://raw.githubusercontent.com/                  ║
# ║      ronaldsexedwards40-glitch/dynabook/main/install-realflow.sh  ║
# ║      | bash                                                       ║
# ║                                                                  ║
# ║  Or, if you already cloned the repo:                              ║
# ║      cd dynabook && sudo bash install-realflow.sh                 ║
# ║                                                                  ║
# ║  It will:                                                        ║
# ║   1. Install Docker + Docker Compose (if missing)                ║
# ║   2. Install Git (if missing)                                    ║
# ║   3. Clone repo to /opt/realflow (or current dir if cloned)      ║
# ║   4. Generate strong random secrets in .env                      ║
# ║   5. docker compose up -d  (FastAPI + MongoDB)                   ║
# ║   6. Print admin login URL + password                            ║
# ║                                                                  ║
# ╚══════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── Pretty output ─────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

h1()   { echo -e "\n${CYAN}╔══════════════════════════════════════════╗\n║ ${BOLD}$1${NC}${CYAN}\n╚══════════════════════════════════════════╝${NC}\n"; }
step() { echo -e "\n${CYAN}[$1]${NC} ${BOLD}$2${NC}"; }
ok()   { echo -e "    ${GREEN}✓${NC} $1"; }
warn() { echo -e "    ${YELLOW}!${NC} $1"; }
err()  { echo -e "    ${RED}✗${NC} $1"; }

REPO_URL="${REPO_URL:-https://github.com/ronaldsexedwards40-glitch/dynabook.git}"
BRANCH="${BRANCH:-main}"
INSTALL_PATH="${INSTALL_PATH:-/opt/realflow}"

h1 "RealFlow One-Click Installer — $(date '+%Y-%m-%d %H:%M')"

# ── Detect platform ───────────────────────────────────────────────
OS=""
case "$(uname -s)" in
    Linux*)  OS="linux";;
    Darwin*) OS="macos";;
    *)       err "Unsupported OS: $(uname -s)"; exit 1;;
esac
ok "Detected OS: $OS"

# ── Detect if we're already inside the repo ────────────────────────
if [ -f "./docker-compose.yml" ] && [ -d "./backend" ] && [ -d "./frontend" ]; then
    INSTALL_PATH="$(pwd)"
    ALREADY_CLONED=1
    ok "Running from inside the repo: $INSTALL_PATH"
else
    ALREADY_CLONED=0
fi

# ── Need root on Linux for system-wide install ────────────────────
if [ "$OS" = "linux" ] && [ "$EUID" -ne 0 ]; then
    warn "Linux install needs root. Re-running with sudo..."
    exec sudo -E bash "$0" "$@"
fi

# ─────────────────────────────────────────────────────────────────
# 1. PREREQUISITES
# ─────────────────────────────────────────────────────────────────
step 1 "Installing prerequisites (git, docker)…"

install_pkg_linux() {
    if command -v apt-get >/dev/null 2>&1; then
        DEBIAN_FRONTEND=noninteractive apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@"
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y -q "$@"
    elif command -v yum >/dev/null 2>&1; then
        yum install -y -q "$@"
    elif command -v pacman >/dev/null 2>&1; then
        pacman -Sy --noconfirm "$@"
    else
        err "No known package manager found. Install manually: $*"
        exit 1
    fi
}

# Git
if ! command -v git >/dev/null 2>&1; then
    warn "Git not found, installing…"
    if [ "$OS" = "linux" ]; then
        install_pkg_linux git
    else
        # macOS — use brew, install if missing
        if ! command -v brew >/dev/null 2>&1; then
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install git
    fi
fi
ok "Git: $(git --version)"

# curl (needed by Docker installer)
if ! command -v curl >/dev/null 2>&1 && [ "$OS" = "linux" ]; then
    install_pkg_linux curl ca-certificates
fi

# Docker
if ! command -v docker >/dev/null 2>&1; then
    warn "Docker not found, installing…"
    if [ "$OS" = "linux" ]; then
        curl -fsSL https://get.docker.com | sh
        systemctl enable --now docker 2>/dev/null || service docker start 2>/dev/null || true
    else
        err "Please install Docker Desktop for Mac manually:"
        err "   https://www.docker.com/products/docker-desktop"
        err "Then re-run this script."
        exit 1
    fi
fi
ok "Docker: $(docker --version)"

# Docker Compose (v2 is bundled with docker on modern installs)
if ! docker compose version >/dev/null 2>&1; then
    warn "Docker Compose plugin not found, installing…"
    if [ "$OS" = "linux" ]; then
        install_pkg_linux docker-compose-plugin || {
            # Fallback: download the binary
            COMPOSE_VERSION="v2.29.7"
            mkdir -p /usr/local/lib/docker/cli-plugins
            curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
                -o /usr/local/lib/docker/cli-plugins/docker-compose
            chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
        }
    fi
fi
ok "Docker Compose: $(docker compose version)"

# Make sure docker daemon is reachable
if ! docker info >/dev/null 2>&1; then
    err "Docker is installed but not running. Start the Docker daemon and re-run."
    exit 1
fi

# ─────────────────────────────────────────────────────────────────
# 2. CLONE OR REUSE THE REPO
# ─────────────────────────────────────────────────────────────────
if [ "$ALREADY_CLONED" = "1" ]; then
    step 2 "Using current directory as install root."
    cd "$INSTALL_PATH"
    # Pull latest from main if we're inside an actual git repo
    if [ -d .git ]; then
        git fetch origin "$BRANCH" 2>/dev/null && git pull --ff-only origin "$BRANCH" 2>/dev/null || \
            warn "Could not fast-forward to origin/$BRANCH — staying on current commit."
    fi
else
    step 2 "Cloning $REPO_URL into $INSTALL_PATH…"
    if [ -d "$INSTALL_PATH" ]; then
        if [ -d "$INSTALL_PATH/.git" ]; then
            warn "Existing install detected — pulling latest…"
            cd "$INSTALL_PATH"
            git fetch origin "$BRANCH"
            git checkout "$BRANCH"
            git pull --ff-only origin "$BRANCH"
        else
            err "$INSTALL_PATH exists and is not a git repo. Remove it or set INSTALL_PATH=… and re-run."
            exit 1
        fi
    else
        git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_PATH"
        cd "$INSTALL_PATH"
    fi
fi
ok "Repo ready at $INSTALL_PATH"

# ─────────────────────────────────────────────────────────────────
# 3. GENERATE .env WITH STRONG SECRETS (only on first install)
# ─────────────────────────────────────────────────────────────────
step 3 "Configuring .env…"

gen_secret() {
    # 48 url-safe chars
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -base64 36 | tr -d '/+=' | cut -c1-48
    else
        head -c 64 /dev/urandom | base64 | tr -d '/+=\n' | cut -c1-48
    fi
}

if [ ! -f .env ]; then
    JWT_SECRET="$(gen_secret)"
    ADMIN_PASS="$(gen_secret | cut -c1-20)"
    POSTBACK="$(gen_secret | cut -c1-32)"
    cat > .env <<EOF
# Generated by install-realflow.sh on $(date '+%Y-%m-%d %H:%M:%S')
DB_NAME=realflow
JWT_SECRET_KEY=${JWT_SECRET}
ADMIN_EMAIL=admin@realflow.local
ADMIN_PASSWORD=${ADMIN_PASS}
POSTBACK_TOKEN=${POSTBACK}
APP_URL=http://localhost:8001
PUBLIC_BASE_URL=http://localhost:8001
CORS_ORIGINS=*

# Optional — fill in if you want email / Google Sheets live-delete
RESEND_API_KEY=
RESEND_FROM=no-reply@realflow.local
GOOGLE_SHEETS_SA_PATH=
GOOGLE_SHEETS_SA_JSON=

# Optional — Cloudflare Tunnel for public exposure (leave empty for local-only)
TUNNEL_TOKEN=
EOF
    ok ".env generated with fresh secrets"
    ok "Admin email:    admin@realflow.local"
    ok "Admin password: $ADMIN_PASS   ← SAVE THIS NOW"
    GENERATED_PASS="$ADMIN_PASS"
else
    ok ".env already exists — keeping existing secrets"
    GENERATED_PASS=""
fi

# ─────────────────────────────────────────────────────────────────
# 4. BUILD + START
# ─────────────────────────────────────────────────────────────────
step 4 "Building Docker images (first run can take 5-10 min)…"
docker compose pull --quiet 2>/dev/null || true
docker compose build

step 5 "Starting RealFlow stack…"
docker compose up -d

# Wait for backend health
echo -n "    waiting for backend"
for i in $(seq 1 60); do
    if curl -sf http://localhost:8001/api/diagnostics/health >/dev/null 2>&1; then
        echo " — ready!"
        break
    fi
    echo -n "."
    sleep 2
done

# ─────────────────────────────────────────────────────────────────
# 5. DONE
# ─────────────────────────────────────────────────────────────────
echo
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    INSTALL COMPLETE                              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo
echo "  Backend API:    http://localhost:8001"
echo "  API Docs:       http://localhost:8001/docs"
echo "  Health Check:   http://localhost:8001/api/diagnostics/health"
echo
echo "  Admin login:    http://localhost:8001/admin-login"
echo "    email     :   admin@realflow.local"
if [ -n "$GENERATED_PASS" ]; then
    echo -e "    password  :   ${BOLD}${YELLOW}${GENERATED_PASS}${NC}   (also in $INSTALL_PATH/.env)"
else
    echo "    password  :   (see ADMIN_PASSWORD in $INSTALL_PATH/.env)"
fi
echo
echo "  Frontend (dev): cd $INSTALL_PATH/frontend && yarn install && yarn start"
echo "                  Then open http://localhost:3000"
echo
echo "  Daily commands:"
echo "    docker compose ps          — status"
echo "    docker compose logs -f     — live logs"
echo "    docker compose restart     — restart stack"
echo "    docker compose down        — stop everything"
echo
echo "  Re-run this script anytime to UPGRADE in place."
echo
