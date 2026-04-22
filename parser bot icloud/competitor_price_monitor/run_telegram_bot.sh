#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_PARENT="$(cd "$PROJECT_ROOT/.." && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv"
ENV_PATH="$PROJECT_ROOT/.env"
EXAMPLE_ENV_PATH="$PROJECT_ROOT/.env.example"

find_python_for_venv() {
  for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if [ ! -f "$ENV_PATH" ] && [ -f "$EXAMPLE_ENV_PATH" ]; then
  cp "$EXAMPLE_ENV_PATH" "$ENV_PATH"
  echo "Создан файл $ENV_PATH. Впишите в него ваш новый Telegram-токен и запустите команду ещё раз."
  exit 1
fi

if [ -f "$ENV_PATH" ]; then
  set -a
  source "$ENV_PATH"
  set +a
fi

if [ -z "${COMPETITOR_PRICE_BOT_TOKEN:-}" ] || [ "$COMPETITOR_PRICE_BOT_TOKEN" = "put_your_telegram_bot_token_here" ]; then
  echo "Не найден Telegram-токен."
  echo "Откройте $ENV_PATH и укажите:"
  echo "COMPETITOR_PRICE_BOT_TOKEN=ваш_новый_токен"
  exit 1
fi

if [ ! -x "$VENV_PATH/bin/python" ]; then
  PYTHON_BIN="$(find_python_for_venv)"
  if [ -z "$PYTHON_BIN" ]; then
    echo "Не удалось найти Python 3."
    exit 1
  fi
  "$PYTHON_BIN" -m venv "$VENV_PATH"
  "$VENV_PATH/bin/pip" install --upgrade pip
  "$VENV_PATH/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"
  "$VENV_PATH/bin/playwright" install chromium
fi

set +e
PYTHONPATH="$PACKAGE_PARENT${PYTHONPATH:+:$PYTHONPATH}" "$VENV_PATH/bin/python" -u -m competitor_price_monitor.telegram_bot "$@"
status=$?
set -e

if [ "$status" -eq 137 ]; then
  echo "Процесс бота был остановлен системой (SIGKILL)."
  echo "Обычно это означает нехватку памяти или ограничение среды запуска."
  echo "Проверьте competitor_price_monitor/logs/telegram_bot.log и попробуйте обычный Terminal/iTerm."
fi

exit "$status"
