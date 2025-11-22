📘 Crypto Algo Pro - User Manual

Choose your language / Оберіть мову:

🇬🇧 English Version

🇺🇦 Українська версія

🇬🇧 English Version

Crypto Algo Pro is an automated trading bot designed to run smoothly in cloud environments like Google Cloud Shell.

1. Setup & Installation

Since Google Cloud Shell already has Python installed, you only need to install the bot's dependencies.

Open the Terminal.

Navigate to the project folder (if not already there):

cd algo-trade-core


Install required libraries:

pip install -r requirements.txt


2. Configuration

You can change trading strategies without touching the code. Use the built-in Cloud Shell Editor to modify the config file.

In the file explorer (left side), open config/settings.json.

Adjust the parameters:

"symbol": The pair to trade (e.g., "BTC/USDT", "ETH/USDT").

"rsi_period": Length of the RSI indicator (default: 14).

"buy_level": Buy signal threshold (e.g., 30).

"sell_level": Sell signal threshold (e.g., 70).

"start_balance": Virtual money for simulation (e.g., 1000).

3. Running the Bot

To start the bot, run this command in the terminal:

python main.py


The bot will start printing logs, price updates, and signals immediately.

4. Monitoring Results (Cloud Shell Specifics)

Since you are in a cloud environment, here is how to view your data:

📉 Viewing Charts:
The bot generates a visual chart after every trade.

Go to the Editor (left sidebar).

Open the data/ folder.

Click on trading_chart.png. The editor will display the image in a new tab.

📝 Viewing Logs:

Open data/trades_history.csv in the Editor to see a table of all executed trades.

5. Stopping the Bot

To stop the program safely, click inside the Terminal and press:
Ctrl + C

🇺🇦 Українська версія

Crypto Algo Pro — це автоматизований торговий бот, адаптований для роботи у хмарних середовищах, таких як Google Cloud Shell.

1. Встановлення

Google Cloud Shell вже має встановлений Python. Вам потрібно лише завантажити бібліотеки проекту.

Відкрийте Термінал.

Перейдіть у папку проекту (якщо ви ще не там):

cd algo-trade-core


Встановіть бібліотеки однією командою:

pip install -r requirements.txt


2. Налаштування (Конфігурація)

Вам не потрібно лізти в код, щоб змінити стратегію. Використовуйте редактор Cloud Shell.

У списку файлів (зліва) відкрийте файл config/settings.json.

Змініть потрібні параметри:

"symbol": Валютна пара (наприклад, "BTC/USDT", "ETH/USDT").

"rsi_period": Період індикатора RSI (стандарт: 14).

"buy_level": Рівень RSI для покупки (наприклад, 30 або 45 для тесту).

"sell_level": Рівень RSI для продажу (наприклад, 70 або 55 для тесту).

"start_balance": Сума віртуальних доларів для тесту (наприклад, 1000).

3. Запуск бота

Щоб запустити програму, введіть у терміналі:

python main.py


Бот одразу почне аналізувати ринок і виводити повідомлення.

4. Перегляд результатів (Особливості Cloud Shell)

Оскільки ви працюєте в браузері, ось як переглядати результати:

📉 Графіки:
Бот малює картинку після кожної угоди.

У панелі файлів зліва відкрийте папку data/.

Клікніть на файл trading_chart.png. Редактор відкриє зображення прямо в правій частині екрана.

📝 Історія угод:

Відкрийте файл data/trades_history.csv, щоб побачити таблицю (Excel-формат) з усіма покупками та продажами.

5. Зупинка

Щоб безпечно зупинити бота, натисніть у вікні терміналу:
Ctrl + C

🇺🇦 Українська верcія