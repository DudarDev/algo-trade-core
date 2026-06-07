#!/bin/bash
set -e

echo "🚀 Починаємо деплой Algo-Trade-Core..."

# Оновлюємо код
git fetch origin
git reset --hard origin/feature/senior-architecture-refactor

echo "📦 Перезбираємо та запускаємо контейнери..."
# Прапорець --remove-orphans видалить старі непотрібні контейнери, якщо вони конфліктують
sudo docker compose -f infrastructure/docker-compose.yml up -d --build --remove-orphans

echo "🗄 Проганяємо міграції бази даних..."
sudo docker exec algo_web python manage.py migrate --noinput

echo "🧹 Очищаємо старі Docker образи..."
sudo docker image prune -f

echo "✅ Деплой успішно завершено!"