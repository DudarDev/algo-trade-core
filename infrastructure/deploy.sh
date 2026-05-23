#!/bin/bash

# Зупиняємо скрипт у разі помилки
set -e

echo "🚀 Починаємо деплой Algo-Trade-Core..."

# 1. Переходимо в папку проєкту
cd ~/algo-trade-core

# 2. Стягуємо останні зміни з гілки (зміни на main, якщо будеш зливати код)
echo "📥 Оновлення коду з GitHub..."
git pull origin feature/senior-architecture-refactor

# 3. Перезбираємо Docker (тільки рушій, щоб не чіпати базу даних)
echo "🏗 Перезбірка Docker контейнерів..."
sudo docker compose -f infrastructure/docker-compose.yml up -d --build engine

# 4. Перезапускаємо веб-панель, щоб оновити кеш дашборду
echo "🌐 Перезапуск веб-панелі..."
sudo docker restart algo_web

echo "✅ Деплой успішно завершено! Бот оновлений і працює."