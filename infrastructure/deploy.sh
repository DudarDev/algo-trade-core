#!/usr/bin/env bash
set -eo pipefail

echo "🚀 [Deploy] Початок автоматичного оновлення Algo-Trade-Core (Systemd Senior Edition)..."

# Визначаємо кореневу папку проєкту
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📂 Робоча директорія: $PROJECT_ROOT"

# 1. Оновлення коду з репозиторію
if [ -d ".git" ]; then
    echo "📥 [Deploy] Отримання останніх змін із Git (origin/main)..."
    git fetch origin main
    git reset --hard origin/main
fi

# 2. Активуємо virtualenv та оновлюємо залежності
if [ -d "venv" ]; then
    echo "📦 [Deploy] Синхронізація Python залежностей..."
    source venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    python src/manage.py collectstatic --noinput || true
fi

# 3. Перезапуск системних сервісів
echo "🔄 [Deploy] Перезапуск системних служб..."
sudo systemctl restart algo-web algo-bot algo-celery algo-telegram algo-tunnel || true

echo "✅ [Deploy] Деплой успішно виконано!"
sleep 2
systemctl is-active algo-web algo-bot algo-celery algo-telegram algo-tunnel
