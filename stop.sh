#!/usr/bin/env bash
# =============================================================================
# PDF RAG Analyzer - Stop Script (Linux / macOS)
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
echo "║         PDF RAG Analyzer  —  Stop Script             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Parse arguments ───────────────────────────────────────────────────────────
REMOVE_VOLUMES=false
REMOVE_IMAGES=false

for arg in "$@"; do
    case "$arg" in
        --volumes|-v)
            REMOVE_VOLUMES=true
            warn "WARNING: --volumes flag set — all persistent data will be deleted!"
            ;;
        --images|-i)
            REMOVE_IMAGES=true
            warn "WARNING: --images flag set — project Docker images will be removed."
            ;;
        --all|-a)
            REMOVE_VOLUMES=true
            REMOVE_IMAGES=true
            warn "WARNING: --all flag set — volumes AND images will be removed (full clean)."
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --volumes, -v    Also remove data volumes  (WARNING: data loss)"
            echo "  --images,  -i    Also remove Docker images"
            echo "  --all,     -a    Remove volumes + images   (full clean)"
            echo "  --help,    -h    Show this help"
            exit 0
            ;;
    esac
done

# =============================================================================
# 1. Check prerequisites
# =============================================================================
step "Checking environment"

if ! command -v docker &>/dev/null; then
    error "Docker not found."
    exit 1
fi

if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    error "Docker Compose not found."
    exit 1
fi
success "Using: $COMPOSE_CMD"

if ! docker info &>/dev/null; then
    error "Docker daemon is not running."
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/docker-compose.yml" ]; then
    error "docker-compose.yml not found. Run this script from the project root."
    exit 1
fi

# =============================================================================
# 2. Show current status
# =============================================================================
step "Current container status"
$COMPOSE_CMD ps 2>/dev/null || true

# =============================================================================
# 3. Stop and remove containers
# =============================================================================
step "Stopping all services"

DOWN_FLAGS="--remove-orphans"
if $REMOVE_VOLUMES; then
    DOWN_FLAGS="$DOWN_FLAGS --volumes"
fi

info "Command: $COMPOSE_CMD down $DOWN_FLAGS"
if $COMPOSE_CMD down $DOWN_FLAGS; then
    success "All containers stopped and removed"
else
    warn "docker compose down reported an error — attempting force stop..."
    $COMPOSE_CMD kill  2>/dev/null || true
    $COMPOSE_CMD rm -f 2>/dev/null || true
    success "Force stop completed"
fi

# =============================================================================
# 4. Optional: remove project images
# =============================================================================
if $REMOVE_IMAGES; then
    step "Removing project Docker images"
    PROJECT_NAME=$(basename "$SCRIPT_DIR" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]-_')
    info "Removing images for project: $PROJECT_NAME"

    # Remove images built by docker compose (tagged with project name)
    IMAGES=$(docker images --filter "reference=${PROJECT_NAME}*" -q 2>/dev/null || true)
    if [ -n "$IMAGES" ]; then
        # shellcheck disable=SC2086
        docker rmi $IMAGES 2>/dev/null && success "Project images removed" || warn "Some images could not be removed (may be in use)"
    else
        info "No project images found to remove"
    fi

    # Also try compose-style image names (project_service)
    for svc in backend frontend; do
        IMG="${PROJECT_NAME}-${svc}"
        if docker image inspect "$IMG" &>/dev/null 2>&1; then
            docker rmi "$IMG" 2>/dev/null && success "Removed image: $IMG" || true
        fi
    done
fi

# =============================================================================
# 5. Verify all project containers are gone
# =============================================================================
step "Verifying shutdown"

CONTAINERS=$(docker ps -a --filter "name=pdf-rag-" --format "{{.Names}}" 2>/dev/null || true)
if [ -z "$CONTAINERS" ]; then
    success "All pdf-rag-* containers have been removed"
else
    warn "The following containers are still present:"
    echo "$CONTAINERS"
    warn "You can force-remove them with: docker rm -f $CONTAINERS"
fi

# =============================================================================
# 6. Summary
# =============================================================================
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║              All services stopped                    ║${NC}"
if $REMOVE_VOLUMES; then
echo -e "${BOLD}${GREEN}║  Data volumes removed (data has been deleted)        ║${NC}"
fi
if $REMOVE_IMAGES; then
echo -e "${BOLD}${GREEN}║  Docker images removed                               ║${NC}"
fi
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}${GREEN}║${NC}  Restart : ${YELLOW}./start.sh${NC}"
echo -e "${BOLD}${GREEN}║${NC}  Rebuild : ${YELLOW}./start.sh --build${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""