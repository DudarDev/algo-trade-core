# 1. Беремо Python
FROM python:3.10-slim

# 2. НАЛАШТУВАННЯ МОВИ (Це виправить помилку з емодзі та укр. мовою)
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
# Виправлення для графіків: вказуємо Matplotlib працювати без екрану
ENV MPLBACKEND=Agg

# 3. Робоча папка
WORKDIR /app

# 4. Бібліотеки
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Код
COPY . .

# 6. Запуск
CMD ["python", "main.py"]