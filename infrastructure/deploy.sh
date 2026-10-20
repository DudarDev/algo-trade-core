#!/usr/bin/env bash
set -eo pipefail

echo "🚀 [Deploy] Початок автоматичного оновлення Algo-Trade-Core..."

# Визначаємо кореневу папку проєкту відносно скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📂 Робоча директорія: $PROJECT_ROOT"

# Оновлення коду
if [ -d ".git" ]; then
    echo "📥 [Deploy] Отримання останніх змін із Git..."
    git pull origin "$(git rev-parse --abbrev-ref HEAD)" || true
fi

# Перезапуск Docker Compose
echo "🐳 [Deploy] Перезбірка та перезапуск контейнерів..."
docker compose -f infrastructure/docker-compose.yml up -d --build --remove-orphans

echo "🧹 [Deploy] Очищення старих невикористовуваних образів..."
docker image prune -f

echo "✅ [Deploy] Деплой успішно виконано!"
docker compose -f infrastructure/docker-compose.yml ps
