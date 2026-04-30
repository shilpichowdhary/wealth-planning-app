#!/usr/bin/env bash
# Restart the wealth-planning backend so it re-reads .env.
# Use this after rotating the Anthropic key or any other secret —
# uvicorn --reload only reloads on code changes, not .env updates.
#
# Usage (from anywhere):
#   ./scripts/restart_backend.sh
#
set -euo pipefail

PORT=${PORT:-8000}
LOG=${LOG:-/tmp/wp-backend.log}

# Resolve project root = parent of this script's directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  echo "error: .venv not found at $PROJECT_ROOT/.venv" >&2
  exit 1
fi
if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
  echo "error: .env not found at $PROJECT_ROOT/.env" >&2
  exit 1
fi

cd "$PROJECT_ROOT"

echo "→ stopping any backend on port $PORT"
pids=$(/usr/sbin/lsof -nP -iTCP:$PORT -sTCP:LISTEN -t 2>/dev/null || true)
if [[ -n "${pids}" ]]; then
  echo "  killing: $pids"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 1
  # shellcheck disable=SC2086
  kill -9 $pids 2>/dev/null || true
  sleep 1
fi

echo "→ starting uvicorn on port $PORT (log: $LOG)"
nohup .venv/bin/uvicorn backend.main:app --reload --port "$PORT" \
  > "$LOG" 2>&1 &
new_pid=$!
disown "$new_pid" 2>/dev/null || true
echo "  pid: $new_pid"

# Wait up to ~8 seconds for "Application startup complete" to appear.
echo "→ waiting for startup"
for _ in $(seq 1 16); do
  if /usr/bin/grep -q "Application startup complete" "$LOG" 2>/dev/null; then
    echo "✓ backend is up"
    /usr/bin/tail -4 "$LOG"
    exit 0
  fi
  if ! kill -0 "$new_pid" 2>/dev/null; then
    echo "✗ backend process exited — check $LOG" >&2
    /usr/bin/tail -20 "$LOG" >&2
    exit 1
  fi
  sleep 0.5
done

echo "✗ backend did not report ready within 8s — check $LOG" >&2
/usr/bin/tail -20 "$LOG" >&2
exit 1
