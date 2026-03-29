#!/bin/bash

echo "📦 1. Пакуємо код (ігноруємо бази даних, логи та сам архів)..."
tar --exclude='./data' \
    --exclude='./bot_data' \
    --exclude='./logs' \
    --exclude='./__pycache__' \
    --exclude='./.git' \
    --exclude='./bot_deploy.tar.gz' \
    -czvf bot_deploy.tar.gz .

echo "📤 2. Відправляємо код на бойовий сервер (VPS)..."
gcloud compute scp bot_deploy.tar.gz paper-trading-bot:~/ --zone=us-central1-c --project=algo-trade-480920

echo "🔄 3. Розпаковуємо, чистимо та перезапускаємо Docker на сервері..."
gcloud compute ssh paper-trading-bot --zone=us-central1-c --project=algo-trade-480920 --command="
    mkdir -p ~/algo-trade-core && \
    tar -xzf bot_deploy.tar.gz -C ~/algo-trade-core && \
    rm bot_deploy.tar.gz && \
    cd ~/algo-trade-core && \
    echo '🧹 Чистимо старі Docker-образи...' && \
    docker system prune -f && \
    echo '🛑 Зупиняємо старі контейнери...' && \
    docker rm -f algo_sniper algo_web dashboard bot site || true && \
    docker-compose down && \
    echo '🔓 Скидаємо базу даних (амністія AutoPruner)...' && \
    rm -f bot_data/bot_data.db && \
    echo '🧠 Видаляємо старі AI-моделі (примусове перенавчання)...' && \
    rm -f bot_data/models/*.pkl && \
    echo '🚀 Запускаємо нову версію...' && \
    docker-compose up -d --build
"

echo "✅ Деплой успішно завершено! Бот зараз почне перенавчатися."
rm bot_deploy.tar.gz