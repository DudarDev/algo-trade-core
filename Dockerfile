FROM python:3.12-slim

# Вимикаємо буферизацію (щоб логи було видно одразу)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Спочатку копіюємо залежності (щоб кешувати цей крок)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Додатково ставимо Django, якщо його немає в requirements
RUN pip install django

# Копіюємо весь код проекту
COPY . .

# Створюємо папку для бази даних
RUN mkdir -p bot_data

# Ця команда буде перезаписана в docker-compose, але хай буде
CMD ["python", "main.py"]