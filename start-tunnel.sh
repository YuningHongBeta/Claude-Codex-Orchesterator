#!/bin/bash
# Start Cloudflare Tunnel to expose local orchestrator API over HTTPS
#
# This creates a public HTTPS URL for your local backend.
# The URL is automatically saved to logs/tunnel.url for use by update-api-url.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"
URL_FILE="$LOGS_DIR/tunnel.url"
LOG_FILE="$LOGS_DIR/tunnel.log"

LOCAL_PORT="${1:-8088}"
PROTOCOL="${2:-http2}"
EDGE_IP_VERSION="${3:-4}"

# Create logs directory
mkdir -p "$LOGS_DIR"

echo "🔗 Starting Cloudflare Tunnel..."
echo "   Local backend: http://localhost:$LOCAL_PORT"
echo "   Protocol: $PROTOCOL"
echo "   Edge IP: IPv$EDGE_IP_VERSION"
echo ""
echo "⏳ Waiting for tunnel URL..."
echo ""

# Clear previous URL
> "$URL_FILE"

# Function to extract and save URL from log
extract_url() {
    while IFS= read -r line; do
        echo "$line"
        echo "$line" >> "$LOG_FILE"
        # Match the trycloudflare.com URL
        if [[ "$line" =~ (https://[a-zA-Z0-9-]+\.trycloudflare\.com) ]]; then
            URL="${BASH_REMATCH[1]}"
            echo "$URL" > "$URL_FILE"
            echo ""
            echo "✅ Tunnel URL saved to: $URL_FILE"
            echo "   Run ./update-api-url.sh to update frontend"
            echo ""
        fi
    done
}

# Run cloudflared and process output
# cloudflared outputs URL to stderr, so redirect stderr to stdout
cloudflared tunnel \
    --protocol "$PROTOCOL" \
    --edge-ip-version "$EDGE_IP_VERSION" \
    --url "http://localhost:$LOCAL_PORT" \
    --loglevel info 2>&1 | extract_url
