FROM python:3.12-slim

# Вимикаємо буферизацію (щоб логи було видно одразу)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Встановлюємо системні залежності для коректної збірки ML-бібліотек
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Копіюємо залежності та встановлюємо їх
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код проекту
COPY . .

# Створюємо папки для логів та баз даних
RUN mkdir -p logs app/data/models bot_data

CMD ["python", "main.py"]
