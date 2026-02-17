#!/bin/bash

echo "📦 1. Пакуємо код (ігноруємо бази даних та логи, щоб не затерти бойові дані)..."
tar --exclude='./data' --exclude='./bot_data' --exclude='./logs' --exclude='./__pycache__' --exclude='./.git' -czvf bot_deploy.tar.gz .

echo "📤 2. Відправляємо код на бойовий сервер (VPS)..."
gcloud compute scp bot_deploy.tar.gz paper-trading-bot:~/ --zone=us-central1-c --project=algo-trade-480920

echo "🔄 3. Розпаковуємо та перезапускаємо Docker на сервері..."
gcloud compute ssh paper-trading-bot --zone=us-central1-c --project=algo-trade-480920 --command="tar -xzvf bot_deploy.tar.gz && docker-compose down && docker-compose up -d --build"

echo "✅ Деплой успішно завершено! Дашборд і Бот оновлені."