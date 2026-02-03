#!/bin/bash
# Update the API URL in frontend files (local dev, local build, and remote)
#
# Usage: ./update-api-url.sh [https://your-tunnel-url.trycloudflare.com]
#
# If no URL is provided, reads from logs/tunnel.url (set by start-tunnel.sh)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
URL_FILE="$SCRIPT_DIR/logs/tunnel.url"
LOG_FILE="$SCRIPT_DIR/logs/tunnel.log"

# Local files to update
LOCAL_DEV="$SCRIPT_DIR/web/index.html"
LOCAL_DIST="$SCRIPT_DIR/web/dist/index.html"

# Remote server (optional - set to empty to skip)
REMOTE_HOST="Lambda"
REMOTE_PATH="public_html/orchestrator/index.html"

# Get API URL from argument or log files
API_URL="$1"
if [ -z "$API_URL" ]; then
    if [ -f "$URL_FILE" ] && [ -s "$URL_FILE" ]; then
        API_URL="$(cat "$URL_FILE" | tail -n 1 | tr -d '\r\n')"
    elif [ -f "$LOG_FILE" ]; then
        API_URL="$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG_FILE" | tail -n 1)"
    fi
fi

if [ -z "$API_URL" ]; then
    echo "❌ No tunnel URL found!"
    echo ""
    echo "Usage: $0 <API_URL>"
    echo "Example: $0 https://abc-xyz.trycloudflare.com"
    echo ""
    echo "Or run ./start-tunnel.sh first to auto-generate logs/tunnel.url"
    exit 1
fi

echo "🔄 Updating API URL to: $API_URL"
echo ""

# Python script to update a file
update_file() {
    local file="$1"
    API_URL="$API_URL" TARGET_FILE="$file" python3 - <<'PY'
import re
import os
from pathlib import Path

path = Path(os.environ.get("TARGET_FILE", ""))
api_url = os.environ.get("API_URL", "")

if not path.exists():
    print(f"   ⚠️  {path} not found, skipping")
    exit(0)

text = path.read_text(encoding="utf-8")
new = re.sub(
    r'window\.ORCHESTRATOR_API_BASE\s*=\s*"[^"]*"',
    f'window.ORCHESTRATOR_API_BASE = "{api_url}"',
    text
)

if text != new:
    path.write_text(new, encoding="utf-8")
    print(f"   ✅ {path}")
else:
    print(f"   ⏭️  {path} (already up to date)")
PY
}

# Update local development file
echo "📁 Local files:"
update_file "$LOCAL_DEV"
update_file "$LOCAL_DIST"

# Update remote file (if configured)
if [ -n "$REMOTE_HOST" ]; then
    echo ""
    echo "🌐 Remote server ($REMOTE_HOST):"
    if ssh -o ConnectTimeout=5 "$REMOTE_HOST" "test -f ~/$REMOTE_PATH" 2>/dev/null; then
        ssh "$REMOTE_HOST" "sed -i.bak 's|window.ORCHESTRATOR_API_BASE = \"[^\"]*\"|window.ORCHESTRATOR_API_BASE = \"$API_URL\"|' ~/$REMOTE_PATH"
        echo "   ✅ ~/$REMOTE_PATH"
    else
        echo "   ⚠️  Remote file not found or connection failed, skipping"
    fi
fi

echo ""
echo "✅ Done! Frontend will now use: $API_URL"
