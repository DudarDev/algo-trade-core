#!/bin/bash
echo "🚀 Запуск деплою Quantum Scalper..."

# Зупиняємо старі контейнери (підтримує обидві версії docker compose)
docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true

# Очищаємо старі логи, якщо потрібно
rm -f logs/*.log 2>/dev/null || true

# Булдуємо та запускаємо новий контейнер
docker compose up -d --build || docker-compose up -d --build

echo "✅ Бот успішно запущений у Docker!"
echo "📄 Щоб подивитися логи, введи: docker logs -f algo_sniper"
