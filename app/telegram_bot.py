import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import threading

class TelegramBot:
    def __init__(self, token, chat_id, trader, strategy_name="RSI"):
        self.bot = telebot.TeleBot(token)
        self.chat_id = chat_id
        self.trader = trader
        self.strategy_name = strategy_name
        self.is_running = True

        # --- КНОПКИ ---
        self.markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn1 = KeyboardButton("💰 Баланс")
        btn2 = KeyboardButton("📊 PnL")      # <--- НОВА КНОПКА
        btn3 = KeyboardButton("📈 Статус")
        btn4 = KeyboardButton("🛑 СТОП")
        self.markup.add(btn1, btn2, btn3, btn4)

        # --- ОБРОБНИКИ ---
        
        @self.bot.message_handler(func=lambda message: message.text == "💰 Баланс")
        def handle_balance(message):
            # Беремо дані з трейдера
            usdt = round(self.trader.usdt, 2)
            crypto = round(self.trader.crypto, 5)
            price = self.trader.last_price
            
            # Рахуємо повну вартість
            total_val, _ = self.trader.get_summary()
            
            msg = (f"💼 **Твій Гаманець:**\n\n"
                   f"💵 USDT: `{usdt}`\n"
                   f"🪙 Crypto: `{crypto}`\n"
                   f"🏷 Ціна зараз: `${price}`\n"
                   f"💰 **Всього: `${total_val:.2f}`**")
            
            self.bot.reply_to(message, msg, parse_mode="Markdown")

        @self.bot.message_handler(func=lambda message: message.text == "📊 PnL")
        def handle_pnl(message):
            # Рахуємо прибуток/збиток
            total_val, pnl_str = self.trader.get_summary()
            pnl = float(pnl_str)
            start = self.trader.start_balance
            
            # Рахуємо відсоток
            if start > 0:
                percent = (pnl / start) * 100
            else:
                percent = 0.0

            emoji = "🚀" if pnl >= 0 else "🔻"
            
            msg = (f"{emoji} **Статистика PnL:**\n\n"
                   f"🏁 Старт: `${start}`\n"
                   f"💰 Зараз: `${total_val:.2f}`\n"
                   f"📊 **PnL: {pnl_str} USDT ({percent:.2f}%)**")
            
            self.bot.reply_to(message, msg, parse_mode="Markdown")

        @self.bot.message_handler(func=lambda message: message.text == "📈 Статус")
        def handle_status(message):
            msg = f"✅ **Бот працює!**\nСтратегія: `{self.strategy_name}`\nРежим: `Paper Trading`"
            self.bot.reply_to(message, msg, parse_mode="Markdown")

        @self.bot.message_handler(func=lambda message: message.text == "🛑 СТОП")
        def handle_stop(message):
            self.bot.reply_to(message, "⚠️ **Зупиняюсь...**", parse_mode="Markdown")
            self.is_running = False

    def start(self):
        print("🎧 Telegram слухає команди...")
        threading.Thread(target=self.bot.infinity_polling, daemon=True).start()
        try:
            self.bot.send_message(self.chat_id, "🎛 **Пульт оновлено (v3.1)**", reply_markup=self.markup)
        except:
            pass
            
    def send_image(self, image_path, caption=""):
        try:
            with open(image_path, 'rb') as img:
                self.bot.send_photo(self.chat_id, img, caption=caption)
        except Exception as e:
            print(f"Помилка TG (Img): {e}")