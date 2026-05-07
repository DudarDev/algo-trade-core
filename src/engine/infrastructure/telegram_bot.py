import os
import sys
import telebot
from telebot import types
import sqlite3
from dotenv import load_dotenv

# Підключаємо корінь проекту для імпорту конфігів
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import Config

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = telebot.TeleBot(TOKEN)
DB_PATH = "bot_data/bot_data.db"
LOCK_FILE = "bot_paused.lock" # Файл, який каже основному боту стояти на паузі

# --- ЗАХИСТ: Перевірка, чи це ти ---
def is_owner(message):
    if str(message.chat.id) != str(CHAT_ID):
        bot.send_message(message.chat.id, "⛔ Доступ заборонено. Це приватний бот.")
        return False
    return True

# --- РОБОТА З БАЗОЮ ДАНИХ (Реальні цифри) ---
def get_real_balance():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Шукаємо останній запис балансу (припускаємо, що таблиця називається paper_balance або подібна)
        # Якщо у тебе інша структура, ми це поправимо
        cursor.execute("SELECT balance FROM sqlite_master WHERE type='table' AND name='paper_balance'")
        if cursor.fetchone():
            cursor.execute("SELECT balance FROM paper_balance ORDER BY id DESC LIMIT 1")
            res = cursor.fetchone()
            return res[0] if res else 1000.0
        return "Невідомо (БД порожня)"
    except Exception as e:
        return f"Помилка: {e}"
    finally:
        if 'conn' in locals(): conn.close()

# --- КЛАВІАТУРИ ---
def main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    # Дивимось, чи стоїть бот на паузі
    status_btn = "▶️ ВІДНОВИТИ ТОРГІВЛЮ" if os.path.exists(LOCK_FILE) else "⏸ ПРИЗУПИНИТИ БОТА"
    
    markup.add(
        types.KeyboardButton("📊 Мій Баланс"),
        types.KeyboardButton("📜 Активні угоди"),
        types.KeyboardButton(status_btn),
        types.KeyboardButton("⚙️ Інфо (Конфіг)")
    )
    return markup

# --- ОБРОБНИКИ КОМАНД ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
    if not is_owner(message): return
    
    status = "⏸ НА ПАУЗІ" if os.path.exists(LOCK_FILE) else "🟢 ПРАЦЮЄ"
    text = (
        f"🤖 **Quantum Scalper Pro**\n\n"
        f"Вітаю, бос!\n"
        f"Статус системи: {status}\n\n"
        f"Оберіть дію на клавіатурі 👇"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📊 Мій Баланс")
def show_balance(message):
    if not is_owner(message): return
    bal = get_real_balance()
    bot.send_message(message.chat.id, f"💰 **Поточний баланс:**\n`{bal} USDT`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "⚙️ Інфо (Конфіг)")
def show_config(message):
    if not is_owner(message): return
    text = (
        f"⚙️ **ПОТОЧНІ НАЛАШТУВАННЯ:**\n\n"
        f"⏱ Таймфрейм: `{Config.TIMEFRAME}`\n"
        f"🎯 Take Profit: `{Config.TAKE_PROFIT_ATR_MULT} ATR`\n"
        f"🛡 Stop Loss: `{Config.STOP_LOSS_ATR_MULT} ATR`\n"
        f"🧠 AI Threshold: `{Config.AI_CONFIDENCE_THRESHOLD}`\n"
        f"💵 Ризик на угоду: `{Config.USDT_PER_TRADE} USDT`\n\n"
        f"*(Щоб змінити їх, відредагуй config.py на сервері)*"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text in ["⏸ ПРИЗУПИНИТИ БОТА", "▶️ ВІДНОВИТИ ТОРГІВЛЮ"])
def toggle_bot(message):
    if not is_owner(message): return
    
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE) # Знімаємо паузу
        bot.send_message(message.chat.id, "🟢 **Бот ВІДНОВИВ сканування ринку!**", reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    else:
        open(LOCK_FILE, 'w').close() # Ставимо на паузу (створюємо пустий файл)
        bot.send_message(message.chat.id, "⏸ **Бот ПРИЗУПИНЕНО.**\nНові угоди відкриватися не будуть (старі ведуться по стопам).", reply_markup=main_menu_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📜 Активні угоди")
def show_trades(message):
    if not is_owner(message): return
    bot.send_message(message.chat.id, "⏳ Функція в розробці... (тут буде список відкритих позицій з БД)")

def run_bot():
    print("🎧 Telegram Control Panel запущено...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

if __name__ == "__main__":
    run_bot()