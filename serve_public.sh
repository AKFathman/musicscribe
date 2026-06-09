#!/usr/bin/env bash
# Launch Vibe Writer locally and expose it on a public cloudflared quick tunnel.
#
#   ./serve_public.sh
#
# Requirements: cloudflared installed (brew install cloudflared), deps installed
# (pip install -r requirements.txt), and ANTHROPIC_API_KEY available in the
# environment or in a .env file in this directory.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"

# Activate venv if present.
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

cleanup() {
  [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null || true
  [ -n "${TUNNEL_PID:-}" ] && kill "$TUNNEL_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting web server on port $PORT…"
PORT="$PORT" HOST=127.0.0.1 python -m vibe_writer.web > /tmp/vibe_web.log 2>&1 &
SERVER_PID=$!
sleep 2

echo "Opening public tunnel…"
cloudflared tunnel --url "http://127.0.0.1:$PORT" > /tmp/vibe_tunnel.log 2>&1 &
TUNNEL_PID=$!

# Wait for cloudflared to print the public URL.
URL=""
for _ in $(seq 1 30); do
  URL=$(grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' /tmp/vibe_tunnel.log | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done

echo
if [ -n "$URL" ]; then
  echo "🎵  Vibe Writer is live at:  $URL"
else
  echo "Tunnel did not report a URL yet — check /tmp/vibe_tunnel.log"
fi
echo "(Ctrl+C to stop the server and tunnel.)"
echo

wait
