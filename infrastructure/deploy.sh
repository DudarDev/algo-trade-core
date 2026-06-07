#!/bin/bash
set -e

echo "🚀 Починаємо деплой Algo-Trade-Core..."

# === КРИТИЧНИЙ ФІКС: Завжди переходимо в папку проєкту ===
cd ~/algo-trade-core
# ==========================================================

# Оновлюємо код
git fetch origin
git reset --hard origin/feature/senior-architecture-refactor

echo "📦 Перезбираємо та запускаємо контейнери..."
sudo docker compose -f infrastructure/docker-compose.yml up -d --build --remove-orphans

echo "🗄 Проганяємо міграції бази даних..."
sudo docker exec algo_web python manage.py migrate --noinput || true

echo "🧹 Очищаємо старі Docker образи..."
sudo docker image prune -f

echo "✅ Деплой успішно завершено!"