#!/bin/bash
# Запуск сайта из этой папки (двойной клик в Finder)
cd "$(dirname "$0")"
echo "Откройте в браузере: http://localhost:5500"
echo "Остановка: Ctrl+C"
open "http://localhost:5500" 2>/dev/null || true
exec python3 -m http.server 5500
