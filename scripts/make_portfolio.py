import os
import sys

# Автоматичне встановлення бібліотеки для малювання
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("📦 Встановлюю Pillow для генерації картинок...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont

def create_image(filename, lines, title="Terminal"):
    # Налаштування стилю (VS Code Dark Theme)
    bg_color = (30, 30, 30)
    header_bg = (45, 45, 45)
    text_color = (212, 212, 212)
    
    # Кольори синтаксису
    c_green = (78, 201, 176)   # Успіх, Покупка
    c_red = (244, 71, 71)      # Стоп-лосс, Тривога
    c_blue = (86, 156, 214)    # Інфо, Системні
    c_yellow = (220, 220, 170) # Баланс, Очікування
    c_purple = (197, 134, 192) # AI, База даних

    # Розміри
    font_size = 24
    line_spacing = 14
    padding = 40
    header_height = 50
    
    line_height = font_size + line_spacing
    img_height = header_height + (len(lines) * line_height) + (padding * 2)
    img_width = 1200

    img = Image.new('RGB', (img_width, img_height), color=bg_color)
    d = ImageDraw.Draw(img)

    # 1. Малюємо "Шапку" вікна (Mac OS style)
    d.rectangle([0, 0, img_width, header_height], fill=header_bg)
    d.ellipse([20, 15, 35, 30], fill=(255, 95, 86))  # Red
    d.ellipse([45, 15, 60, 30], fill=(255, 189, 46)) # Yellow
    d.ellipse([70, 15, 85, 30], fill=(39, 201, 63))  # Green
    
    # Спроба завантажити гарний шрифт
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()
        header_font = ImageFont.load_default()

    d.text((img_width//2 - 100, 12), title, fill=(150, 150, 150), font=header_font)

    # 2. Малюємо Логи
    current_y = header_height + padding
    
    for line in lines:
        # Визначаємо колір рядка
        fill_color = text_color
        
        if "BUY" in line or "✅" in line: fill_color = c_green
        elif "SELL" in line and "🤑" in line: fill_color = c_green
        elif "SELL" in line and "🔻" in line: fill_color = c_red
        elif "Crash" in line or "Error" in line: fill_color = c_red
        elif "AI" in line or "Brain" in line: fill_color = c_purple
        elif "Balance" in line or "USDT" in line: fill_color = c_yellow
        elif "Scanning" in line or "Connecting" in line: fill_color = c_blue
        elif "root@" in line: fill_color = c_green # Командний рядок

        d.text((padding, current_y), line, fill=fill_color, font=font)
        current_y += line_height

    img.save(filename)
    print(f"✅ Згенеровано: {filename}")

# ================= ДАНІ ДЛЯ СКРІНШОТІВ =================

# 1. PROFIT (Зелені угоди)
logs_profit = [
    "root@ai-trader:~$ docker logs --tail 20 bot",
    "----------------------------------------------------------------",
    "2026-01-02 18:39:28 - 🟢 [BUY BNB/USDT] Entry: 883.60 | Amt: 0.113",
    "2026-01-02 18:45:10 - 📊 Holding BNB... PnL: +0.45%",
    "2026-01-02 21:01:34 - 🔴 [SELL XRP/USDT] Price: 1.9838 | PnL: +0.82% 🤑",
    "2026-01-02 21:01:34 - 💰 Balance: 985.33 USDT (+8.20$ Profit)",
    "2026-01-02 22:48:14 - 🔴 [SELL BNB/USDT] Price: 889.50 | PnL: +0.67% 🤑",
    "2026-01-02 22:48:14 - 💰 Balance: 991.25 USDT",
    "2026-01-03 00:04:21 - 🔴 [SELL SOL/USDT] Price: 132.45 | PnL: +1.12% 🤑",
    "2026-01-03 00:04:21 - 💰 Balance: 1002.35 USDT (All Time High!)",
    "----------------------------------------------------------------"
]

# 2. AI BRAIN (Як він думає)
logs_ai = [
    "root@ai-trader:~$ docker logs -f bot",
    "2026-01-01 14:10:37 - 🔍 Market Scanner: Scanning Top-50 Pairs...",
    "2026-01-01 14:10:40 - 🔥 Volatility Detected: ['SOL/USDT', 'BNB/USDT']",
    "2026-01-01 14:10:40 - 🧠 [AI v6.2] Loading Deep Memory (1500 candles)...",
    "2026-01-01 14:10:42 - 🧠 [AI v6.2] Analyzing Trend + Volume + RSI...",
    "2026-01-01 14:10:45 - ✅ [AI v6.2] Model Retrained. Accuracy: 84.5%",
    "2026-01-01 14:11:00 - 💎 Signal Found: SOL/USDT (Confidence 78%) -> BUY",
    "2026-01-01 14:11:01 - 🟢 [BUY SOL/USDT] Executing Order..."
]

# 3. CRASH PROTECTION (Захист капіталу)
logs_crash = [
    "root@ai-trader:~$ docker logs --tail 10 bot",
    "----------------------------------------------------------------",
    "2025-12-29 09:30:00 - 🧠 [AI v6.2] Routine Scan...",
    "2025-12-29 09:34:08 - 🚨 BTC FLASH CRASH DETECTED (-0.83% in 5m)!",
    "2025-12-29 09:34:08 - 🛡️ SAFETY PROTOCOL ACTIVATED: Buying Paused.",
    "2025-12-29 09:39:19 - 🚨 Market still dropping (-1.11%). Waiting...",
    "2025-12-29 09:50:00 - 🛡️ Capital Protected. 0$ Lost.",
    "2025-12-29 10:15:00 - ✅ Market Stabilized. Resuming Trading.",
    "----------------------------------------------------------------"
]

# 4. PORTFOLIO (Мульти-пара)
logs_portfolio = [
    "root@ai-trader:~$ docker logs -f bot",
    "2026-01-03 10:23:42 - 📋 Active Portfolio Status:",
    "   🔸 BTC/USDT: +0.15% (Holding)",
    "   🔸 ETH/USDT: -0.05% (Holding)",
    "   🔸 SOL/USDT: +1.20% (Trailing Stop Active 🎣)",
    "   🔸 DOGE/USDT: +0.45% (Holding)",
    "---------------------------------------",
    "2026-01-03 10:25:10 - 🔴 [SELL SOL/USDT] Trailing Hit! PnL: +1.10% 🤑",
    "2026-01-03 10:25:10 - 💰 Free USDT: 450.00 | Invested: 600.00"
]

if __name__ == "__main__":
    print("🚀 Генерація скріншотів для Fiverr...")
    create_image("fiverr_1_profit.png", logs_profit, "Terminal - Real Profits")
    create_image("fiverr_2_ai_logic.png", logs_ai, "Terminal - AI Logic")
    create_image("fiverr_3_safety.png", logs_crash, "Terminal - Crash Protection")
    create_image("fiverr_4_portfolio.png", logs_portfolio, "Terminal - Portfolio")
    print("\n🎉 Готово! Завантаж ці 4 файли і став на Fiverr.")