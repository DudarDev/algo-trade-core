#!/bin/bash

echo "🛑 --- КРОК 1: ЗБЕРЕЖЕННЯ ДАНИХ ---"
# Спробуємо знайти базу в різних місцях і зберегти її
if docker cp bot:/app/data/bot_data.db ./backup_bot_data.db 2>/dev/null; then
    echo "✅ Базу знайдено в /app/data/ і збережено як backup_bot_data.db"
elif docker cp bot:/app/bot_data/bot_data.db ./backup_bot_data.db 2>/dev/null; then
    echo "✅ Базу знайдено в /app/bot_data/ і збережено як backup_bot_data.db"
else
    echo "⚠️ УВАГА: Базу не знайдено в контейнері! Якщо це перший запуск - ігноруйте."
fi

echo "🗑️ --- КРОК 2: ОЧИЩЕННЯ СТАРОЇ СИСТЕМИ ---"
# Використовуємо нову команду (без дефісу) або стару як запасний варіант
docker compose down 2>/dev/null || docker-compose down 2>/dev/null
# Добиваємо вручну, якщо щось лишилось
docker stop bot website 2>/dev/null
docker rm bot website 2>/dev/null

echo "📂 --- КРОК 3: ПІДГОТОВКА СПІЛЬНОЇ ПАПКИ ---"
mkdir -p ./bot_data
chmod 777 ./bot_data

echo "🔙 --- КРОК 4: ВІДНОВЛЕННЯ БАЗИ ---"
if [ -f "./backup_bot_data.db" ]; then
    cp ./backup_bot_data.db ./bot_data/bot_data.db
    # Робимо копію для сумісності з Django
    cp ./backup_bot_data.db ./bot_data/db.sqlite3
    echo "✅ Базу даних відновлено в спільну папку."
else
    echo "⚠️ Бекап відсутній. Буде створено нову порожню базу."
fi

echo "🚀 --- КРОК 5: ЗАПУСК НОВОЇ АРХІТЕКТУРИ ---"
# Спробуємо запустити через нову команду (V2)
if docker compose up -d; then
    echo "✅ Запущено через 'docker compose' (V2)"
else
    echo "⚠️ 'docker compose' не спрацював, пробуємо стару 'docker-compose'..."
    docker-compose up -d
fi

echo "🔧 --- КРОК 6: НАЛАШТУВАННЯ ПРАВ ---"
# Фінальна перевірка прав всередині контейнерів
docker exec -u 0 bot chmod -R 777 /app/bot_data 2>/dev/null
docker exec -u 0 website chmod -R 777 /app/bot_data 2>/dev/null

echo "🎉 --- ГОТОВО! ---"
echo "Перевірка логів бота: docker logs -f bot"