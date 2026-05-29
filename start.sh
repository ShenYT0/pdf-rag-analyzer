#!/usr/bin/env bash
# =============================================================================
# PDF RAG Analyzer - Start Script (Linux / macOS)
# =============================================================================
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERR ]${NC}  $*" >&2; }
step()    { echo -e "\n${BOLD}${CYAN}>> $*${NC}"; }

# ── Resolve project root ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║         PDF RAG Analyzer  —  Start Script            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Parse arguments ───────────────────────────────────────────────────────────
BUILD_FLAG=""
DETACH_FLAG="-d"

for arg in "$@"; do
    case "$arg" in
        --build|-b)    BUILD_FLAG="--build" ;;
        --foreground)  DETACH_FLAG="" ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --build, -b      Force rebuild of Docker images"
            echo "  --foreground     Run in foreground (no -d flag)"
            echo "  --help, -h       Show this help"
            exit 0
            ;;
    esac
done

# =============================================================================
# 1. Check prerequisites
# =============================================================================
step "Checking prerequisites"

# Docker
if ! command -v docker &>/dev/null; then
    error "Docker not found. Install it from: https://docs.docker.com/get-docker/"
    exit 1
fi
success "Docker: $(docker --version)"

# Docker Compose (plugin v2 or standalone v1)
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    success "Docker Compose: $(docker compose version)"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
    success "Docker Compose: $(docker-compose --version)"
else
    error "Docker Compose not found. Install it from: https://docs.docker.com/compose/install/"
    exit 1
fi

# Docker daemon
if ! docker info &>/dev/null; then
    error "Docker daemon is not running. Start it first:"
    echo "  sudo systemctl start docker   # systemd"
    echo "  sudo service docker start     # SysV"
    exit 1
fi
success "Docker daemon is running"

# =============================================================================
# 2. System resource checks
# =============================================================================
step "Checking system resources"

# Available memory (Milvus recommends >= 8 GB)
if [ -f /proc/meminfo ]; then
    AVAIL_MEM_KB=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
    TOTAL_MEM_KB=$(awk '/MemTotal/{print $2}'     /proc/meminfo)
    TOTAL_GB=$(echo "scale=1; $TOTAL_MEM_KB/1048576" | bc 2>/dev/null || echo "?")
    AVAIL_GB=$(echo "scale=1; $AVAIL_MEM_KB/1048576" | bc 2>/dev/null || echo "?")
    info "Memory: total ${TOTAL_GB} GB, available ${AVAIL_GB} GB"
    if [ "${AVAIL_MEM_KB:-0}" -gt 0 ] && [ "${AVAIL_MEM_KB}" -lt 4194304 ]; then
        warn "Less than 4 GB available — Milvus may be unstable (8 GB+ recommended)"
    fi
fi

# Disk space
DISK_AVAIL=$(df -BG "$SCRIPT_DIR" 2>/dev/null | awk 'NR==2{gsub("G","",$4); print $4}' || echo 0)
info "Disk space available in project directory: ${DISK_AVAIL} GB"
if [ "${DISK_AVAIL:-0}" -lt 10 ] 2>/dev/null; then
    warn "Less than 10 GB free — consider freeing disk space before starting"
fi

# vm.max_map_count (required by Milvus / Elasticsearch)
MAX_MAP=$(cat /proc/sys/vm/max_map_count 2>/dev/null || echo 0)
if [ "${MAX_MAP:-0}" -lt 262144 ]; then
    warn "vm.max_map_count=${MAX_MAP} (Milvus requires >= 262144)"
    warn "Fix temporarily : sudo sysctl -w vm.max_map_count=262144"
    warn "Fix permanently : echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf"
fi

# =============================================================================
# 3. Environment file setup
# =============================================================================
step "Checking environment configuration"

ENV_FILE="$SCRIPT_DIR/backend/.env"
ENV_EXAMPLE="$SCRIPT_DIR/backend/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        warn "backend/.env not found — copying from .env.example"
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        warn "Please edit backend/.env (set your API keys, model names, etc.) then re-run."
        echo ""
        echo -e "  ${YELLOW}nano $ENV_FILE${NC}"
        echo ""
        # Continue with defaults; user can edit and restart
    else
        error "Neither backend/.env nor backend/.env.example found."
        error "Create backend/.env before starting."
        exit 1
    fi
else
    success "backend/.env found"
fi

# Frontend .env (optional)
FE_ENV="$SCRIPT_DIR/frontend/.env"
FE_ENV_EXAMPLE="$SCRIPT_DIR/frontend/.env.example"
if [ ! -f "$FE_ENV" ] && [ -f "$FE_ENV_EXAMPLE" ]; then
    cp "$FE_ENV_EXAMPLE" "$FE_ENV"
    success "frontend/.env created from .env.example"
elif [ -f "$FE_ENV" ]; then
    success "frontend/.env found"
fi

# =============================================================================
# 4. Verify docker-compose.yml
# =============================================================================
step "Verifying project files"

if [ ! -f "$SCRIPT_DIR/docker-compose.yml" ]; then
    error "docker-compose.yml not found. Run this script from the project root."
    exit 1
fi
success "docker-compose.yml found"

# =============================================================================
# 5. Start services
# =============================================================================
step "Starting services"

info "Command: $COMPOSE_CMD up $DETACH_FLAG $BUILD_FLAG"
echo ""

if ! $COMPOSE_CMD up $DETACH_FLAG $BUILD_FLAG; then
    error "Failed to start services. Check the output above for details."
    echo ""
    info "Useful diagnostic commands:"
    echo "  $COMPOSE_CMD logs          # all service logs"
    echo "  $COMPOSE_CMD logs backend  # backend logs only"
    echo "  $COMPOSE_CMD ps            # container status"
    exit 1
fi

# =============================================================================
# 6. Wait for backend health (detached mode only)
# =============================================================================
if [ -n "$DETACH_FLAG" ]; then
    step "Waiting for services to become ready"

    BACKEND_HEALTH="http://localhost:8000/health"
    MAX_WAIT=120
    INTERVAL=5
    ELAPSED=0

    info "Polling backend health endpoint (timeout: ${MAX_WAIT}s) ..."
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        if curl -sf "$BACKEND_HEALTH" &>/dev/null; then
            echo ""
            success "Backend is ready"
            break
        fi
        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))
        printf "."
    done
    echo ""

    if [ $ELAPSED -ge $MAX_WAIT ]; then
        warn "Backend did not respond within ${MAX_WAIT}s — it may still be initializing."
        warn "Run '$COMPOSE_CMD logs -f backend' to monitor startup."
    fi

    # ==========================================================================
    # 7. Summary
    # ==========================================================================
    step "Service status"
    echo ""
    $COMPOSE_CMD ps
    echo ""

    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║           Services started — access URLs              ║${NC}"
    echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}${GREEN}║${NC}  Frontend UI  :  ${CYAN}http://localhost${NC}"
    echo -e "${BOLD}${GREEN}║${NC}  Backend API  :  ${CYAN}http://localhost:8000${NC}"
    echo -e "${BOLD}${GREEN}║${NC}  API Docs     :  ${CYAN}http://localhost:8000/docs${NC}"
    echo -e "${BOLD}${GREEN}║${NC}  Neo4j Browser:  ${CYAN}http://localhost:7474${NC}"
    echo -e "${BOLD}${GREEN}║${NC}  MinIO Console:  ${CYAN}http://localhost:9001${NC}"
    echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}${GREEN}║${NC}  Stop  : ${YELLOW}./stop.sh${NC}"
    echo -e "${BOLD}${GREEN}║${NC}  Logs  : ${YELLOW}docker compose logs -f${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
fi