# Використовуємо офіційний легкий образ Python
FROM python:3.12-slim

# Вимикаємо буферизацію логів та генерацію .pyc файлів
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Встановлюємо системні залежності для коректної збірки ML-бібліотек
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Спочатку копіюємо requirements.txt для кешування шару Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код проєкту
COPY . .

# Створюємо правильні папки для нової архітектури
RUN mkdir -p logs data_storage/models data_storage/history

# Запуск оркестратора
CMD ["python", "main.py"]