#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
python="$repo_root/.venv/bin/python"

if [ ! -x "$python" ]; then
  if command -v python3 >/dev/null 2>&1; then
    python="python3"
  else
    printf 'error: expected %s or python3 on PATH\n' "$repo_root/.venv/bin/python" >&2
    exit 127
  fi
fi

export PYTHONPATH="$repo_root/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$python" -m lane.cli "$@"
