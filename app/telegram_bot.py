import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import threading
import time

class TelegramBot:
    def __init__(self, token, chat_id, trader, strategy_name="RSI"):
        self.bot = telebot.TeleBot(token)
        self.chat_id = chat_id
        self.trader = trader  # Ми даємо боту доступ до гаманця!
        self.strategy_name = strategy_name
        self.is_running = True

        # --- СТВОРЕННЯ КНОПОК ---
        self.markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn1 = KeyboardButton("💰 Баланс")
        btn2 = KeyboardButton("📈 Статус")
        btn3 = KeyboardButton("🛑 СТОП")
        self.markup.add(btn1, btn2, btn3)

        # --- ОБРОБНИКИ КОМАНД (Що робити при натисканні) ---
        
        @self.bot.message_handler(func=lambda message: message.text == "💰 Баланс")
        def handle_balance(message):
            # Бот лізе в гаманець і дивиться суму
            usdt = round(self.trader.usdt, 2)
            crypto = round(self.trader.crypto, 5)
            # Рахуємо загальну вартість (приблизно, по останній ціні покупки)
            msg = f"💼 **Твій Гаманець:**\n\n💵 USDT: `{usdt}`\n🪙 Crypto: `{crypto}`"
            self.bot.reply_to(message, msg, parse_mode="Markdown")

        @self.bot.message_handler(func=lambda message: message.text == "📈 Статус")
        def handle_status(message):
            msg = f"✅ **Бот працює!**\nСтратегія: `{self.strategy_name}`\nРежим: `Paper Trading`"
            self.bot.reply_to(message, msg, parse_mode="Markdown")

        @self.bot.message_handler(func=lambda message: message.text == "🛑 СТОП")
        def handle_stop(message):
            self.bot.reply_to(message, "⚠️ **Отримана команда зупинки!**\nБот завершує роботу...", parse_mode="Markdown")
            # Тут ми ставимо прапорець, щоб main.py знав, що треба вимикатися
            self.is_running = False

    def start(self):
        """Запускає слухача Телеграму в окремому потоці"""
        print("🎧 Telegram слухає команди...")
        # Запускаємо polling в фоні (threading), щоб не блокувати торгівлю
        threading.Thread(target=self.bot.infinity_polling, daemon=True).start()
        
        # Відправляємо стартове меню
        try:
            self.bot.send_message(self.chat_id, "🎛 **Пульт керування активовано!**", reply_markup=self.markup)
        except:
            pass

    def send_message(self, text):
        """Для відправки сигналів (як раніше)"""
        try:
            self.bot.send_message(self.chat_id, text, parse_mode="Markdown")
        except Exception as e:
            print(f"Помилка TG: {e}")

    def send_image(self, image_path, caption=""):
        """Для відправки графіків"""
        try:
            with open(image_path, 'rb') as img:
                self.bot.send_photo(self.chat_id, img, caption=caption)
        except Exception as e:
            print(f"Помилка TG (Img): {e}")