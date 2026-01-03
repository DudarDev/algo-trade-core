import telebot
from telebot import types
import os
import threading
import time
from dotenv import load_dotenv

# Завантаження змінних оточення
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = telebot.TeleBot(TOKEN)

# --- ГЛОБАЛЬНІ ЗМІННІ (Стан бота) ---
bot_status = "STOPPED"  # STOPPED / RUNNING
current_pair = "BTC/USDT"
current_risk = "Medium"  # Low / Medium / High

# --- КЛАВІАТУРИ (Меню) ---


def main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("🚀 СТАРТ / СТОП")
    btn2 = types.KeyboardButton("⚙️ Налаштування")
    btn3 = types.KeyboardButton("📊 Баланс & PnL")
    btn4 = types.KeyboardButton("📈 Графік")
    markup.add(btn1, btn2, btn3, btn4)
    return markup


def settings_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    # Ряд 1: Вибір монети
    btn_btc = types.InlineKeyboardButton("BTC/USDT", callback_data="set_pair_BTC")
    btn_eth = types.InlineKeyboardButton("ETH/USDT", callback_data="set_pair_ETH")
    btn_sol = types.InlineKeyboardButton("SOL/USDT", callback_data="set_pair_SOL")
    markup.row(btn_btc, btn_eth, btn_sol)

    # Ряд 2: Ризик (змінює Stop-Loss)
    btn_low = types.InlineKeyboardButton("🛡 Low Risk", callback_data="set_risk_low")
    btn_high = types.InlineKeyboardButton("🔥 High Risk", callback_data="set_risk_high")
    markup.row(btn_low, btn_high)

    return markup


# --- ОБРОБНИКИ КОМАНД ---


@bot.message_handler(commands=["start"])
def send_welcome(message):
    welcome_text = (
        f"🤖 **Crypto Algo Pro v3.5**\n\n"
        f"Вітаю, {message.from_user.first_name}!\n"
        f"Цей бот готовий до автоматичної торгівлі.\n\n"
        f"🔹 **Поточна пара:** {current_pair}\n"
        f"🔹 **Режим:** Paper Trading (Симуляція)\n"
    )
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda message: message.text == "⚙️ Налаштування")
def open_settings(message):
    text = (
        "🛠 **ПАНЕЛЬ НАЛАШТУВАНЬ**\n\n"
        "Тут ви можете змінити торгову пару та рівень ризику без перезапуску бота.\n"
        f"Поточний вибір: **{current_pair}** | Ризик: **{current_risk}**"
    )
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=settings_inline_keyboard(),
        parse_mode="Markdown",
    )


# --- ОБРОБКА КЛІКІВ ПО КНОПКАХ (Callback) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global current_pair, current_risk

    if call.data.startswith("set_pair_"):
        new_pair = call.data.split("_")[2] + "/USDT"
        current_pair = new_pair
        bot.answer_callback_query(call.id, f"Пару змінено на {new_pair}")
        bot.send_message(
            call.message.chat.id,
            f"✅ **Торгова пара змінена:** {current_pair}",
            parse_mode="Markdown",
        )

    elif call.data.startswith("set_risk_"):
        risk_level = call.data.split("_")[2]
        current_risk = risk_level.capitalize()
        bot.answer_callback_query(call.id, f"Ризик змінено на {current_risk}")
        bot.send_message(
            call.message.chat.id,
            f"⚠️ **Рівень ризику змінено:** {current_risk}",
            parse_mode="Markdown",
        )


# --- СТАНДАРТНІ КНОПКИ ---


@bot.message_handler(func=lambda message: message.text == "🚀 СТАРТ / СТОП")
def toggle_bot(message):
    global bot_status
    if bot_status == "STOPPED":
        bot_status = "RUNNING"
        bot.send_message(
            message.chat.id,
            f"🟢 **Бот ЗАПУЩЕНИЙ!**\nПрацюємо з парою: {current_pair}",
            parse_mode="Markdown",
        )
    else:
        bot_status = "STOPPED"
        bot.send_message(
            message.chat.id, "🔴 **Бот ЗУПИНЕНИЙ!**", parse_mode="Markdown"
        )


@bot.message_handler(func=lambda message: message.text == "📊 Баланс & PnL")
def show_balance(message):
    # Тут має бути виклик реальної функції з paper_trader.py
    # Для прикладу - заглушка
    text = (
        "💰 **Ваш Гаманець:**\n"
        "USDT: 1050.00 (+5.0%)\n"
        f"В активах: 0.00 {current_pair.split('/')[0]}"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == "📈 Графік")
def send_chart_request(message):
    bot.send_message(message.chat.id, "⏳ Малюю графік, зачекайте...")
    # Тут логіка відправки фото
    # with open('data/trading_chart.png', 'rb') as photo:
    #    bot.send_photo(message.chat.id, photo)


# --- ЗАПУСК ---
def run_bot():
    print("🎧 Telegram Bot слухає команди...")
    bot.infinity_polling()


if __name__ == "__main__":
    run_bot()
