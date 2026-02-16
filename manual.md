# 📘 AI Crypto Scalper Pro (v12) — Інструкція користувача

Це професійний торговий бот на базі штучного інтелекту, що працює у контейнерах Docker.

## 1. Як це працює
Система складається з двох частин:
1. **AI Brain (Бот):** Аналізує ринок, прогнозує рух ціни та відкриває угоди.
2. **Web Dashboard (Сайт):** Показує статистику, графіки та стан бота у реальному часі.

## 2. Керування Ботом (Docker)

Оскільки ви використовуєте Cloud Shell та Docker, основні команди виконуються в терміналі.

### 🟢 Запуск / Перезавантаження (Оновлення)
Щоб оновити бота до останньої версії або перезапустити:
```bash
# 1. Зупинити старе
docker stop bot website
docker rm bot website

# 2. Очистити кеш (важливо для e2-micro!)
docker system prune -a -f

# 3. Завантажити нову версію
docker pull us-central1-docker.pkg.dev/algo-trade-480920/bot-repo/ai-scalper:v12

# 4. Запустити БОТА
docker run -d --name bot --restart=always \
  -v $(pwd)/bot_data:/app/bot_data \
  us-central1-docker.pkg.dev/algo-trade-480920/bot-repo/ai-scalper:v12 python main.py

# 5. Запустити САЙТ (Dashboard)
docker run -d --name website --restart=always \
  -p 8000:8000 \
  -v $(pwd)/bot_data:/app/bot_data \
  --link bot \
  us-central1-docker.pkg.dev/algo-trade-480920/bot-repo/ai-scalper:v12 python manage.py runserver 0.0.0.0:8000