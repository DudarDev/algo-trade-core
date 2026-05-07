#!/bin/bash

# Зупиняємо скрипт при будь-якій помилці
set -e

echo "🚀 Починаємо розгортання Quantum Scalper..."

# Переконуємось, що ми в правильній директорії
cd "$(dirname "$0")"

echo "📦 Збираємо нові Docker-образи..."
docker compose build --no-cache

echo "🛑 Зупиняємо старі контейнери..."
docker compose down

echo "🟢 Запускаємо бота у фоновому режимі..."
docker compose up -d

echo "✅ Успішно розгорнуто! Показую логи (Ctrl+C щоб вийти)..."
docker compose logs -f trading-bot