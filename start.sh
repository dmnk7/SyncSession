#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

VENV="$ROOT/venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-6767}"
URL="http://${HOST}:${PORT}"

free_port() {
  local pids
  pids="$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi

  echo "Port ${PORT} ist belegt, beende Prozess(e): $(echo "$pids" | tr '\n' ' ')"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true

  local i=0
  while (( i < 10 )); do
    pids="$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
      echo "Port ${PORT} ist wieder frei."
      return 0
    fi
    sleep 0.2
    i=$((i + 1))
  done

  pids="$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "Prozess reagiert nicht, force kill: $(echo "$pids" | tr '\n' ' ')"
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

if [[ ! -x "$PYTHON" ]]; then
  echo "venv fehlt, lege sie an..."
  python3 -m venv "$VENV"
fi

echo "Installiere requirements..."
"$PIP" install -r "$ROOT/requirements.txt"

free_port

printf '\nApp starten:\n'
printf '\033]8;;%s\033\\%s\033]8;;\033\\\n' "$URL" "$URL"
printf '%s:%s\n\n' "$HOST" "$PORT"

cd "$ROOT/SyncSession"
exec "$PYTHON" manage.py runserver "${HOST}:${PORT}"
