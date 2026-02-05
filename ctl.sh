#!/bin/bash
#
# Orchestrator Control Script
# Unified CLI for managing the Claude×Codex Orchestrator
#
# Usage: ./ctl.sh <command> [options]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"
URL_FILE="$LOGS_DIR/tunnel.url"
LOG_FILE="$LOGS_DIR/tunnel.log"
PID_DIR="$LOGS_DIR/pids"

# Default settings
DEFAULT_PORT=8088
REMOTE_HOST="Lambda"
REMOTE_PATH="public_html/orchestrator"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

#=============================================================================
# Helper Functions
#=============================================================================

log_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

log_success() {
    echo -e "${GREEN}✅${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠️${NC}  $1"
}

log_error() {
    echo -e "${RED}❌${NC} $1"
}

ensure_dirs() {
    mkdir -p "$LOGS_DIR" "$PID_DIR"
}

#=============================================================================
# Command: help
#=============================================================================

show_help() {
    cat << 'EOF'
🎼 Orchestrator Control Script

Usage: ./ctl.sh <command> [options]

Commands:
  start [port]      Start backend + tunnel (default port: 8088)
  stop              Stop all running services
  status            Show status of services

  backend [port]    Start backend server only
  tunnel [port]     Start tunnel only
  update-url [url]  Update API URL in frontend files

  dev               Start frontend dev server (npm run dev)
  build             Build frontend for production
  deploy            Deploy frontend to remote server

  mount             Mount remote filesystem (sshfs/rsync)
  unmount           Unmount remote filesystem
  remote-status     Show SSH remote status
  remote-setup      Install macFUSE + sshfs via Homebrew

  logs [service]    Show logs (backend|tunnel|all)
  help              Show this help message

Examples:
  ./ctl.sh start              # Start everything on port 8088
  ./ctl.sh start 9000         # Start on custom port
  ./ctl.sh backend 8088       # Start only backend
  ./ctl.sh tunnel 8088        # Start only tunnel
  ./ctl.sh update-url         # Update frontend with tunnel URL
  ./ctl.sh stop               # Stop all services
  ./ctl.sh status             # Check what's running
  ./ctl.sh remote-status      # Check SSH remote configuration
  ./ctl.sh mount              # Mount remote filesystem

EOF
}

#=============================================================================
# Command: backend
#=============================================================================

cmd_backend() {
    local port="${1:-$DEFAULT_PORT}"
    local run_in_bg="${2:-false}"

    ensure_dirs

    echo ""
    echo "🎼 Starting Orchestrator Backend..."
    echo "   Port: $port"
    echo "   CORS: enabled for all origins"
    echo ""

    if [ "$run_in_bg" = "true" ]; then
        python3 "$SCRIPT_DIR/web_server.py" \
            --host 0.0.0.0 \
            --port "$port" \
            --cors-origin '*' \
            > "$LOGS_DIR/backend.log" 2>&1 &
        echo $! > "$PID_DIR/backend.pid"
        log_success "Backend started (PID: $(cat "$PID_DIR/backend.pid"))"
    else
        echo "API endpoints:"
        echo "   GET  /api/jobs         - List all jobs"
        echo "   GET  /api/jobs/{id}    - Get job details"
        echo "   POST /api/jobs         - Create new job"
        echo ""
        echo "Press Ctrl+C to stop."
        echo ""
        python3 "$SCRIPT_DIR/web_server.py" \
            --host 0.0.0.0 \
            --port "$port" \
            --cors-origin '*'
    fi
}

#=============================================================================
# Command: tunnel
#=============================================================================

cmd_tunnel() {
    local port="${1:-$DEFAULT_PORT}"
    local run_in_bg="${2:-false}"

    ensure_dirs

    echo ""
    echo "🔗 Starting Cloudflare Tunnel..."
    echo "   Local backend: http://localhost:$port"
    echo ""

    # Clear previous URL
    > "$URL_FILE"

    # Function to extract and save URL
    extract_url() {
        while IFS= read -r line; do
            echo "$line"
            echo "$line" >> "$LOG_FILE"
            if [[ "$line" =~ (https://[a-zA-Z0-9-]+\.trycloudflare\.com) ]]; then
                local url="${BASH_REMATCH[1]}"
                echo "$url" > "$URL_FILE"
                echo ""
                log_success "Tunnel URL: $url"
                log_info "Run './ctl.sh update-url' to update frontend"
                echo ""
            fi
        done
    }

    if [ "$run_in_bg" = "true" ]; then
        # Background mode with URL extraction
        (
            cloudflared tunnel \
                --protocol http2 \
                --edge-ip-version 4 \
                --url "http://localhost:$port" \
                --loglevel info 2>&1 | while IFS= read -r line; do
                    echo "$line" >> "$LOG_FILE"
                    if [[ "$line" =~ (https://[a-zA-Z0-9-]+\.trycloudflare\.com) ]]; then
                        echo "${BASH_REMATCH[1]}" > "$URL_FILE"
                    fi
                done
        ) &
        echo $! > "$PID_DIR/tunnel.pid"
        log_info "Tunnel starting in background (PID: $(cat "$PID_DIR/tunnel.pid"))"
        log_info "Waiting for URL..."

        # Wait for URL (max 30 seconds)
        for i in {1..30}; do
            if [ -s "$URL_FILE" ]; then
                echo ""
                log_success "Tunnel URL: $(cat "$URL_FILE")"
                break
            fi
            sleep 1
        done
    else
        cloudflared tunnel \
            --protocol http2 \
            --edge-ip-version 4 \
            --url "http://localhost:$port" \
            --loglevel info 2>&1 | extract_url
    fi
}

#=============================================================================
# Command: update-url
#=============================================================================

cmd_update_url() {
    local api_url="$1"

    # Get URL from argument or files
    if [ -z "$api_url" ]; then
        if [ -f "$URL_FILE" ] && [ -s "$URL_FILE" ]; then
            api_url="$(cat "$URL_FILE" | tail -n 1 | tr -d '\r\n')"
        elif [ -f "$LOG_FILE" ]; then
            api_url="$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG_FILE" | tail -n 1)"
        fi
    fi

    if [ -z "$api_url" ]; then
        log_error "No tunnel URL found!"
        echo ""
        echo "Usage: ./ctl.sh update-url <URL>"
        echo "   or: Run './ctl.sh tunnel' first"
        exit 1
    fi

    echo ""
    log_info "Updating API URL to: $api_url"
    echo ""

    # Update function
    update_file() {
        local file="$1"
        API_URL="$api_url" TARGET_FILE="$file" python3 - <<'PY'
import re, os
from pathlib import Path

path = Path(os.environ.get("TARGET_FILE", ""))
api_url = os.environ.get("API_URL", "")

if not path.exists():
    print(f"   ⚠️  {path.name} not found, skipping")
    exit(0)

text = path.read_text(encoding="utf-8")
new = re.sub(
    r'window\.ORCHESTRATOR_API_BASE\s*=\s*"[^"]*"',
    f'window.ORCHESTRATOR_API_BASE = "{api_url}"',
    text
)

if text != new:
    path.write_text(new, encoding="utf-8")
    print(f"   ✅ {path.name}")
else:
    print(f"   ⏭️  {path.name} (already up to date)")
PY
    }

    echo "📁 Local files:"
    update_file "$SCRIPT_DIR/web/index.html"
    update_file "$SCRIPT_DIR/web/dist/index.html"

    # Remote update (optional)
    if [ -n "$REMOTE_HOST" ]; then
        echo ""
        echo "🌐 Remote server ($REMOTE_HOST):"
        if ssh -o ConnectTimeout=5 "$REMOTE_HOST" "test -f ~/$REMOTE_PATH/index.html" 2>/dev/null; then
            ssh "$REMOTE_HOST" "sed -i.bak 's|window.ORCHESTRATOR_API_BASE = \"[^\"]*\"|window.ORCHESTRATOR_API_BASE = \"$api_url\"|' ~/$REMOTE_PATH/index.html"
            echo "   ✅ index.html"
        else
            echo "   ⚠️  Not available or not configured"
        fi
    fi

    echo ""
    log_success "Frontend will now use: $api_url"
}

#=============================================================================
# Command: start (backend + tunnel)
#=============================================================================

cmd_start() {
    local port="${1:-$DEFAULT_PORT}"

    ensure_dirs

    echo ""
    echo "🎼 Starting Orchestrator (port: $port)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Start backend in background
    cmd_backend "$port" "true"

    sleep 1

    # Start tunnel in background
    cmd_tunnel "$port" "true"

    sleep 2

    # Auto-update URL if available
    if [ -s "$URL_FILE" ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        cmd_update_url
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_success "All services started!"
    echo ""
    echo "   Backend: http://localhost:$port"
    if [ -s "$URL_FILE" ]; then
        echo "   Tunnel:  $(cat "$URL_FILE")"
    fi
    echo ""
    echo "   Run './ctl.sh stop' to stop all services"
    echo "   Run './ctl.sh status' to check status"
    echo ""
}

#=============================================================================
# Command: stop
#=============================================================================

cmd_stop() {
    echo ""
    log_info "Stopping services..."

    local stopped=0

    if [ -f "$PID_DIR/backend.pid" ]; then
        local pid=$(cat "$PID_DIR/backend.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            log_success "Backend stopped (PID: $pid)"
            stopped=$((stopped + 1))
        fi
        rm -f "$PID_DIR/backend.pid"
    fi

    if [ -f "$PID_DIR/tunnel.pid" ]; then
        local pid=$(cat "$PID_DIR/tunnel.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            # Also kill child processes (cloudflared)
            pkill -P "$pid" 2>/dev/null || true
            log_success "Tunnel stopped (PID: $pid)"
            stopped=$((stopped + 1))
        fi
        rm -f "$PID_DIR/tunnel.pid"
    fi

    # Also try to kill any remaining cloudflared processes for this project
    pkill -f "cloudflared.*localhost:${DEFAULT_PORT}" 2>/dev/null || true

    if [ $stopped -eq 0 ]; then
        log_info "No services were running"
    fi
    echo ""
}

#=============================================================================
# Command: status
#=============================================================================

cmd_status() {
    echo ""
    echo "📊 Service Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Backend
    if [ -f "$PID_DIR/backend.pid" ]; then
        local pid=$(cat "$PID_DIR/backend.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "   Backend:  ${GREEN}Running${NC} (PID: $pid)"
        else
            echo -e "   Backend:  ${RED}Stopped${NC} (stale PID file)"
            rm -f "$PID_DIR/backend.pid"
        fi
    else
        echo -e "   Backend:  ${YELLOW}Not started${NC}"
    fi

    # Tunnel
    if [ -f "$PID_DIR/tunnel.pid" ]; then
        local pid=$(cat "$PID_DIR/tunnel.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "   Tunnel:   ${GREEN}Running${NC} (PID: $pid)"
            if [ -s "$URL_FILE" ]; then
                echo "             URL: $(cat "$URL_FILE")"
            fi
        else
            echo -e "   Tunnel:   ${RED}Stopped${NC} (stale PID file)"
            rm -f "$PID_DIR/tunnel.pid"
        fi
    else
        echo -e "   Tunnel:   ${YELLOW}Not started${NC}"
    fi

    echo ""
}

#=============================================================================
# Command: dev
#=============================================================================

cmd_dev() {
    echo ""
    log_info "Starting frontend dev server..."
    echo ""
    cd "$SCRIPT_DIR/web"
    npm run dev
}

#=============================================================================
# Command: build
#=============================================================================

cmd_build() {
    echo ""
    log_info "Building frontend..."
    echo ""
    cd "$SCRIPT_DIR/web"
    npm run build
    echo ""
    log_success "Build complete: web/dist/"
}

#=============================================================================
# Command: deploy
#=============================================================================

cmd_deploy() {
    local web_dist="$SCRIPT_DIR/web/dist"

    echo ""
    log_info "Deploying to $REMOTE_HOST:~/$REMOTE_PATH..."

    if [ ! -d "$web_dist" ]; then
        log_error "web/dist not found. Run './ctl.sh build' first."
        exit 1
    fi

    # Create remote directory
    ssh "$REMOTE_HOST" "mkdir -p ~/$REMOTE_PATH"

    # Sync files
    rsync -avz --delete "$web_dist/" "$REMOTE_HOST:~/$REMOTE_PATH/"

    echo ""
    log_success "Deployment complete!"
    log_info "Don't forget to run './ctl.sh start' for the backend"
    echo ""
}

#=============================================================================
# Command: logs
#=============================================================================

cmd_logs() {
    local service="${1:-all}"

    case "$service" in
        backend)
            if [ -f "$LOGS_DIR/backend.log" ]; then
                tail -f "$LOGS_DIR/backend.log"
            else
                log_error "No backend logs found"
            fi
            ;;
        tunnel)
            if [ -f "$LOG_FILE" ]; then
                tail -f "$LOG_FILE"
            else
                log_error "No tunnel logs found"
            fi
            ;;
        all|*)
            echo "=== Backend ==="
            tail -20 "$LOGS_DIR/backend.log" 2>/dev/null || echo "(no logs)"
            echo ""
            echo "=== Tunnel ==="
            tail -20 "$LOG_FILE" 2>/dev/null || echo "(no logs)"
            ;;
    esac
}

#=============================================================================
# Command: mount (SSH remote)
#=============================================================================

cmd_mount_remote() {
    echo ""
    log_info "Mounting remote filesystem..."
    echo ""
    python3 "$SCRIPT_DIR/ssh_remote_cli.py" mount
}

#=============================================================================
# Command: unmount (SSH remote)
#=============================================================================

cmd_unmount_remote() {
    echo ""
    log_info "Unmounting remote filesystem..."
    echo ""
    python3 "$SCRIPT_DIR/ssh_remote_cli.py" unmount
}

#=============================================================================
# Command: remote-status
#=============================================================================

cmd_remote_status() {
    echo ""
    python3 "$SCRIPT_DIR/ssh_remote_cli.py" status
    echo ""
}

#=============================================================================
# Command: remote-setup (install macFUSE + sshfs)
#=============================================================================

cmd_remote_setup() {
    echo ""
    log_info "Installing macFUSE and sshfs..."
    echo ""

    if ! command -v brew &>/dev/null; then
        log_error "Homebrew is required. Install from https://brew.sh"
        exit 1
    fi

    log_info "Installing macFUSE (requires restart after install)..."
    brew install --cask macfuse

    log_info "Installing sshfs..."
    brew install sshfs

    echo ""
    log_success "Installation complete!"
    log_warn "You may need to restart your Mac for macFUSE to work."
    log_info "Run './ctl.sh remote-status' to verify."
    echo ""
}

#=============================================================================
# Main
#=============================================================================

cd "$SCRIPT_DIR"

case "${1:-help}" in
    start)
        cmd_start "$2"
        ;;
    stop)
        cmd_stop
        ;;
    status)
        cmd_status
        ;;
    backend)
        cmd_backend "$2"
        ;;
    tunnel)
        cmd_tunnel "$2"
        ;;
    update-url|update)
        cmd_update_url "$2"
        ;;
    dev)
        cmd_dev
        ;;
    build)
        cmd_build
        ;;
    deploy)
        cmd_deploy
        ;;
    mount)
        cmd_mount_remote
        ;;
    unmount)
        cmd_unmount_remote
        ;;
    remote-status)
        cmd_remote_status
        ;;
    remote-setup)
        cmd_remote_setup
        ;;
    logs)
        cmd_logs "$2"
        ;;
    help|--help|-h|*)
        show_help
        ;;
esac
