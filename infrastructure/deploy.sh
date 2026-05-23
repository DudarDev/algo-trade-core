#!/bin/bash
set -e
echo "🚀 Починаємо деплой Algo-Trade-Core..."
cd ~/algo-trade-core
git pull origin feature/senior-architecture-refactor
sudo docker compose -f infrastructure/docker-compose.yml up -d --build engine
echo "✅ Деплой успішно завершено!"
