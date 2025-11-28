# 👇 ЗМІНА ТУТ: Ставимо Python 3.12, бо цього вимагає pandas_ta
FROM python:3.12-slim

# Налаштування кодування та буфера
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
# Для графіків без екрану
ENV MPLBACKEND=Agg

# Робоча папка
WORKDIR /app

# Бібліотеки
COPY requirements.txt .
# --break-system-packages потрібен для нових версій Python у Docker
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Код
COPY . .

# Запуск
CMD ["python", "main.py"]
