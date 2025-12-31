from PIL import Image, ImageDraw, ImageFont
import os

def create_terminal_screenshot(filename, lines, title="Terminal - ai-bot"):
    width = 1100
    line_height = 40
    padding = 50
    header_height = 50
    height = (len(lines) * line_height) + (padding * 2) + header_height
    
    bg_color = (30, 30, 30)
    text_color = (200, 200, 200)
    green_color = (78, 201, 176)
    red_color = (244, 71, 71) 
    yellow_color = (220, 220, 170)
    blue_color = (86, 156, 214) 
    
    img = Image.new('RGB', (width, height), color=bg_color)
    d = ImageDraw.Draw(img)

    # Header
    d.rectangle([0, 0, width, header_height], fill=(50, 50, 50))
    d.text((20, 15), f"🔴 🟡 🟢  {title}", fill=(200, 200, 200))

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 22)
    except:
        font = ImageFont.load_default()

    y = header_height + padding
    for line in lines:
        color = text_color
        if "BUY" in line: color = blue_color
        if "SELL" in line and "🤑" in line: color = green_color
        if "SELL" in line and "🔻" in line: color = red_color
        if "Crash Detected" in line: color = red_color # АКЦЕНТ НА ЗАХИСТІ
        if "Balance" in line: color = yellow_color

        d.text((padding, y), line, fill=color, font=font)
        y += line_height

    img.save(filename)
    print(f"✅ Картинка {filename} готова!")

# --- ТВОЇ РЕАЛЬНІ ЛОГИ ---
logs_safety = [
    "root@bot-server:~$ docker logs --tail 20 ai-bot",
    "----------------------------------------------------------------",
    "2025-12-29 05:30:30 - 🔴 [SELL LTC/USDT] Price: 80.21 | PnL: +0.13% 🤑",
    "2025-12-29 05:30:30 - 💰 Balance: 1000.75 USDT",
    "2025-12-29 09:30:00 - 🧠 [AI v4.0] Scanning market volatility...",
    "2025-12-29 09:34:08 - 🚨 BTC Crash Detected (-0.83% drop). BUYING BLOCKED!",
    "2025-12-29 09:39:19 - 🚨 BTC Crash Detected (-1.11% drop). BUYING BLOCKED!",
    "2025-12-29 09:44:30 - 🚨 BTC Crash Detected (-0.95% drop). Protection Active.",
    "2025-12-29 09:55:00 - 🛡️ Capital Protected. Waiting for market stability...",
    "2025-12-29 11:28:16 - 🟢 [BUY SOL/USDT] Entry: 125.30 (Market Stabilized)",
    "----------------------------------------------------------------"
]

if __name__ == "__main__":
    try:
        from PIL import Image
    except ImportError:
        os.system("pip install Pillow")
    create_terminal_screenshot("proof_safety_first.png", logs_safety, "Terminal - AI Crash Protection")