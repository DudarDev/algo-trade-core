import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict

# Завантажуємо .env з кореня проекту
load_dotenv()

class Config:
    PROJECT_NAME = "AlgoTradeCore_Pro"
    VERSION = "8.1.0_Safe_Mode"  # Оновлено для режиму безпеки
    
    # 🔧 ШЛЯХИ: 
    BASE_DIR = Path(__file__).resolve().parent.parent
    
    # --- Security & Notifications ---
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # --- ARBITRAGE CONFIGURATION ---
    # Список бірж для моніторингу цін.
    EXCHANGES: List[str] = ['binanceus', 'kraken', 'coinbase']
    
    # Словник ключів для кожної біржі
    EXCHANGE_KEYS: Dict[str, Dict[str, str]] = {
        'binanceus': {
            'apiKey': os.getenv("BINANCE_API_KEY", ""),
            'secret': os.getenv("BINANCE_API_SECRET", "")
        },
        'kraken': {
            'apiKey': os.getenv("KRAKEN_API_KEY", ""),
            'secret': os.getenv("KRAKEN_API_SECRET", "")
        },
        'coinbase': {
            'apiKey': os.getenv("COINBASE_API_KEY", ""),
            'secret': os.getenv("COINBASE_API_SECRET", "")
        }
    }

    # Мінімальний % різниці в ціні, щоб угода була вигідною
    ARBITRAGE_MIN_SPREAD_PCT = 1.5  
    
    # --- Trading Targets ---
    # Якщо True - торгуємо віртуальними грошима (безпечно)
    IS_PAPER_TRADING = os.getenv("IS_PAPER_TRADING", "True").lower() == "true"
    
    # Монети, які ми шукаємо (XRP та DOGE залишаємо, але під суворим наглядом AI)
    SYMBOLS: List[str] = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 
        'SHIB/USDT', 'DOGE/USDT', 'XRP/USDT', 'LTC/USDT'
    ]
    
    # Чорний список (Монети, які "зливали" депозит у логах)
    BLACKLIST: List[str] = [
        'HYPE/USDT', 'PAXG/USDT', 'USDC/USDT', 'FDUSD/USDT', 
        'PUMP/USDT', 'ZEC/USDT', 'HBAR/USDT', 'PEPE/USDT'
    ] 
    
    TIMEFRAME = "1m" # 1 хвилина для швидкої реакції
    
    # --- Risk Management (ОНОВЛЕНО) ---
    MAX_OPEN_POSITIONS = 1      # Тільки 1 угода одночасно (консервативно)
    USDT_PER_TRADE = 50.0       
    POSITION_SIZE_FRACTION = 0.95 
    
    # Динамічні стопи (ATR)
    STOP_LOSS_ATR_MULT = 1.5    # Трохи ширше, щоб не вибивало шумом
    TAKE_PROFIT_ATR_MULT = 2.5  
    
    # --- AI & Filters (ВАЖЛИВО) ---
    DATA_DIR = BASE_DIR / "data"
    MODEL_DIR = DATA_DIR / "models"
    LOG_DIR = BASE_DIR / "logs"
    
    # ПОРІГ ВХОДУ: Підняли до 0.72 (Бот стріляє тільки напевно)
    AI_CONFIDENCE_THRESHOLD = 0.72 
    
    # ФІЛЬТР ФЛЕТУ (ADX): Якщо менше 20, ринок стоїть на місці -> не торгуємо
    ADX_THRESHOLD = 20 

    MIN_TRAINING_SAMPLES = 500      
    TRAINING_LOOKBACK = 1000 
    
    @classmethod
    def setup_environment(cls):
        """Автоматично створює папки при старті."""
        for path in [cls.MODEL_DIR, cls.LOG_DIR, cls.DATA_DIR]:
            path.mkdir(parents=True, exist_ok=True)
            
    @classmethod
    def validate_keys(cls):
        """Перевірка наявності ключів для основної біржі."""
        if not cls.EXCHANGE_KEYS['binanceus']['apiKey']:
            print("⚠️  УВАГА: Основні ключі Binance не знайдені в .env!")

# Запуск налаштування папок при імпорті
Config.setup_environment()