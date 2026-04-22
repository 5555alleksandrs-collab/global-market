#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_PARENT="$(cd "$PROJECT_ROOT/.." && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv"
DEFAULT_CONFIG="$PROJECT_ROOT/config/settings.yaml"

if [ ! -f "$DEFAULT_CONFIG" ]; then
  DEFAULT_CONFIG="$PROJECT_ROOT/config/settings.example.yaml"
fi

if [ ! -x "$VENV_PATH/bin/python" ]; then
  python3 -m venv "$VENV_PATH"
  "$VENV_PATH/bin/pip" install --upgrade pip
  "$VENV_PATH/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"
  "$VENV_PATH/bin/playwright" install chromium
fi

CONFIG_PATH="$DEFAULT_CONFIG"

if [ "${1:-}" != "" ] && [[ "${1:-}" != --* ]]; then
  CONFIG_PATH="$1"
  shift
fi

exec env PYTHONPATH="$PACKAGE_PARENT${PYTHONPATH:+:$PYTHONPATH}" "$VENV_PATH/bin/python" -m competitor_price_monitor --config "$CONFIG_PATH" "$@"
