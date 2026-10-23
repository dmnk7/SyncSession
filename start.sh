#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

VENV="$ROOT/venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
URL="http://${HOST}:${PORT}"

if [[ ! -x "$PYTHON" ]]; then
  echo "venv fehlt, lege sie an..."
  python3 -m venv "$VENV"
fi

echo "Installiere requirements..."
"$PIP" install -r "$ROOT/requirements.txt"

printf '\nApp starten:\n'
printf '\033]8;;%s\033\\%s\033]8;;\033\\\n' "$URL" "$URL"
printf '%s:%s\n\n' "$HOST" "$PORT"

cd "$ROOT/SyncSession"
exec "$PYTHON" manage.py runserver "${HOST}:${PORT}"
