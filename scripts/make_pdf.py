from fpdf import FPDF
import os

class PDF(FPDF):
    def header(self):
        # Header на кожній сторінці
        self.set_font('Arial', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'AI Trading System v6.2 - Professional Performance Report', 0, 1, 'R')
        self.ln(5)

    def footer(self):
        # Номер сторінки знизу
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        # Заголовки секцій
        self.set_font('Arial', 'B', 16)
        self.set_text_color(0, 51, 102) # Dark Blue
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)

    def chapter_body(self, body):
        # Текст
        self.set_font('Arial', '', 11)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 6, body)
        self.ln(5)

    def add_screenshot(self, image_path, caption):
        # Вставка картинки, якщо вона існує
        if os.path.exists(image_path):
            # Центрування картинки
            self.image(image_path, x=15, w=180)
            self.ln(2)
            self.set_font('Arial', 'I', 9)
            self.set_text_color(100, 100, 100)
            self.cell(0, 5, caption, 0, 1, 'C')
            self.ln(10)
        else:
            print(f"⚠️ Warning: Image {image_path} not found. Skipping.")

# --- СТВОРЕННЯ ДОКУМЕНТА ---

pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()

# 1. ТИТУЛЬНА СТОРІНКА
pdf.set_font('Arial', 'B', 26)
pdf.set_text_color(0, 0, 0)
pdf.ln(40)
pdf.cell(0, 20, 'AI CRYPTO TRADING BOT', 0, 1, 'C')
pdf.set_font('Arial', '', 16)
pdf.cell(0, 10, 'Technical Analysis & Performance Review', 0, 1, 'C')
pdf.ln(20)
pdf.set_font('Arial', 'B', 12)
pdf.cell(0, 10, 'Version: 6.2 (Stable)', 0, 1, 'C')
pdf.cell(0, 10, 'Strategy: Gradient Boosting AI + Smart Exit', 0, 1, 'C')
pdf.ln(30)
# Тут можна додати логотип, якщо є
# pdf.image('logo.png', x=80, w=50) 

# 2. ВСТУП
pdf.add_page()
pdf.chapter_title('1. Executive Summary')
pdf.chapter_body(
    "This system is not just a standard trading script. It is a fully autonomous algorithmic trading engine powered by Machine Learning. "
    "Unlike basic RSI/MACD bots that fail during market volatility, this bot utilizes a Gradient Boosting model to analyze complex patterns including volume, trend, and volatility."
)

# 3. ПРИБУТКОВІСТЬ
pdf.chapter_title('2. Live Trading Performance')
pdf.chapter_body(
    "The bot operates on a 5-minute timeframe, executing high-probability scalp trades. "
    "The 'Smart Exit' logic ensures that trades are closed with profit before the market reverses. "
    "Below is a log from a live server session showing consecutive profitable trades."
)
pdf.add_screenshot('fiverr_1_profit.png', 'Fig 1. Real-time trading logs showing consistent profit generation.')

# 4. ШТУЧНИЙ ІНТЕЛЕКТ
pdf.add_page()
pdf.chapter_title('3. AI & Machine Learning Core')
pdf.chapter_body(
    "The heart of the system is the AI Brain (v6.2). It doesn't rely on hardcoded rules. "
    "Instead, it retrains itself every few hours based on the latest market data (Deep Memory of 1500+ candles). "
    "This allows the bot to adapt to both Bull and Bear markets automatically."
)
pdf.add_screenshot('fiverr_2_ai_logic.png', 'Fig 2. AI model retraining process and signal detection.')

# 5. БЕЗПЕКА
pdf.chapter_title('4. Risk Management: Crash Protection')
pdf.chapter_body(
    "Capital preservation is the #1 priority. The bot includes a 'Crash Protection' module that monitors Bitcoin's global trend. "
    "If a sudden market dump is detected, the bot instantly freezes all buying activities to prevent losses."
)
pdf.add_screenshot('fiverr_3_safety.png', 'Fig 3. The system detecting a market crash and pausing operations.')

# 6. ПОРТФЕЛЬ
pdf.add_page()
pdf.chapter_title('5. Autonomous Portfolio Management')
pdf.chapter_body(
    "The bot includes an Auto-Scanner that monitors the top 50 cryptocurrencies. "
    "It automatically selects the top 10 most volatile and liquid pairs to trade, ensuring your capital is always working on the best assets."
)
pdf.add_screenshot('fiverr_4_portfolio.png', 'Fig 4. Multi-pair portfolio management.')

# 7. ТЕХНІЧНИЙ СТЕК
pdf.ln(10)
pdf.chapter_title('6. Technical Specifications')
specs = (
    "- Language: Python 3.12 (Async)\n"
    "- ML Framework: Scikit-learn (Gradient Boosting)\n"
    "- Infrastructure: Docker / Google Cloud Platform\n"
    "- Database: SQLite (Persistent Data)\n"
    "- Interface: Django Web Dashboard + Telegram Alerts"
)
pdf.chapter_body(specs)

pdf.ln(20)
pdf.set_font('Arial', 'B', 14)
pdf.set_text_color(0, 100, 0)
pdf.cell(0, 10, 'Proven Performance. Transparent Logic. Fully Automated.', 0, 1, 'C')

# Збереження
pdf.output('AI_Bot_Performance_Report.pdf', 'F')
print("✅ PDF успішно створено: AI_Bot_Performance_Report.pdf")