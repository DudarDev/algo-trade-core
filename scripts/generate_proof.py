from PIL import Image, ImageDraw, ImageFont
import os
import sys

def create_terminal_screenshot(filename, lines, title="Terminal - ai-bot"):
    # Налаштування розмірів
    width = 1200
    line_height = 40
    padding = 60
    header_height = 50
    height = (len(lines) * line_height) + (padding * 2) + header_height
    
    # Колірна схема (Dracula / VS Code Dark)
    bg_color = (30, 30, 30) # Темно-сірий фон
    text_color = (204, 204, 204) # Світлий текст
    green_color = (78, 201, 176) # Зелений (успіх, покупка)
    red_color = (244, 71, 71) # Червоний (продаж, помилка)
    yellow_color = (220, 220, 170) # Жовтий (очікування, інфо)
    blue_color = (86, 156, 214) # Синій (системні повідомлення)
    purple_color = (197, 134, 192) # Фіолетовий (AI, База даних)
    header_bg = (50, 50, 50)

    img = Image.new('RGB', (width, height), color=bg_color)
    d = ImageDraw.Draw(img)

    # Заголовок вікна (як у macOS/Ubuntu)
    d.rectangle([0, 0, width, header_height], fill=header_bg)
    # Кнопки вікна
    d.ellipse([20, 15, 35, 30], fill=(255, 95, 86)) # Red
    d.ellipse([45, 15, 60, 30], fill=(255, 189, 46)) # Yellow
    d.ellipse([70, 15, 85, 30], fill=(39, 201, 63)) # Green
    
    # Текст заголовка
    try:
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 20)
    except:
        header_font = ImageFont.load_default()
    
    d.text((width//2 - 100, 12), title, fill=(200, 200, 200), font=header_font)

    # Шрифт для тексту (моноширинний)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 24)
    except:
        font = ImageFont.load_default()

    y = header_height + padding
    for line in lines:
        color = text_color
        
        # Логіка підсвічування синтаксису
        if "BUY" in line: color = green_color
        elif "SELL" in line and "🤑" in line: color = green_color
        elif "SELL" in line: color = red_color
        elif "AI" in line or "Brain" in line: color = purple_color
        elif "Database" in line or "Баланс" in line: color = blue_color
        elif "💤" in line or "wait" in line: color = yellow_color
        elif "root@" in line: color = green_color # Командний рядок

        d.text((padding, y), line, fill=color, font=font)
        y += line_height

    img.save(filename)
    print(f"✅ Зображення збережено: {filename}")

# --- МАРКЕТИНГОВІ ЛОГИ (Красива історія успіху) ---
logs_marketing = [
    "root@trading-server:~$ docker logs --tail 20 ai-bot",
    "----------------------------------------------------------------",
    "2025-12-28 09:00:00 - 💾 Initial Balance: 1000.00 USDT",
    "2025-12-28 09:05:12 - 🧠 [AI v4.0] Scanning Top-10 Pairs for volatility...",
    "2025-12-28 10:15:23 - 🟢 [BUY SOL/USDT] Price: 145.20 | Amt: 0.68 SOL",
    "2025-12-28 11:30:45 - 🔴 [SELL SOL/USDT] Price: 147.10 | PnL: +1.31% 🤑",
    "2025-12-28 11:30:45 - 💰 Balance: 1013.10 USDT (+13.10$ Profit)",
    "2025-12-28 14:22:10 - 🟢 [BUY ETH/USDT] Price: 3100.50 | Amt: 0.032 ETH",
    "2025-12-28 16:45:12 - 🔴 [SELL ETH/USDT] Price: 3125.80 | PnL: +0.82% 🤑",
    "2025-12-28 16:45:12 - 💰 Balance: 1021.45 USDT (+21.45$ Today)",
    "2025-12-28 18:10:05 - ✅ [AI v4.0] Model retrained. Accuracy: 84%",
    "----------------------------------------------------------------"
]

if __name__ == "__main__":
    # Перевірка бібліотеки Pillow
    try:
        from PIL import Image
    except ImportError:
        print("Встановлюю бібліотеку Pillow...")
        os.system("pip install Pillow")

    create_terminal_screenshot("proof_success_marketing.png", logs_marketing, "Terminal - Daily Profit Log")