import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict

# Завантажуємо .env з кореня проекту
load_dotenv()

class Config:
    PROJECT_NAME = "AlgoTradeCore_Pro"
    VERSION = "8.0.0_Arbitrage_Alpha" # Перехід на арбітражну версію
    
    # 🔧 ШЛЯХИ: 
    BASE_DIR = Path(__file__).resolve().parent.parent
    
    # --- Security & Notifications ---
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # --- ARBITRAGE CONFIGURATION (NEW) ---
    # Список бірж для моніторингу цін.
    # Важливо: Вибирай біржі, які доступні в твоєму регіоні (US).
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
    # (Враховуючи комісії за вивід та торгівлю на обох біржах)
    ARBITRAGE_MIN_SPREAD_PCT = 1.5  
    
    # --- Trading Targets ---
    IS_PAPER_TRADING = os.getenv("IS_PAPER_TRADING", "True").lower() == "true"
    
    # Монети, які ми шукаємо на всіх біржах
    SYMBOLS: List[str] = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 
        'SHIB/USDT', 'DOGE/USDT', 'XRP/USDT', 'LTC/USDT'
    ]
    
    BLACKLIST: List[str] = [
        'HYPE/USDT', 'PAXG/USDT', 'USDC/USDT', 'FDUSD/USDT', 
        'PUMP/USDT', 'ZEC/USDT', 'HBAR/USDT'
    ] 
    
    TIMEFRAME = "1m" # Для арбітражу потрібна швидша реакція
    
    # --- Risk Management ---
    MAX_OPEN_POSITIONS = 2 # Зменшили, щоб не забити канал
    USDT_PER_TRADE = 50.0      
    POSITION_SIZE_FRACTION = 0.95 
    
    STOP_LOSS_ATR_MULT = 1.2   
    TAKE_PROFIT_ATR_MULT = 2.0 
    
    # --- AI Settings (Залишаємо як допоміжний інструмент) ---
    DATA_DIR = BASE_DIR / "data"
    MODEL_DIR = DATA_DIR / "models"
    LOG_DIR = BASE_DIR / "logs"
    
    AI_CONFIDENCE_THRESHOLD = 0.65  
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

Config.setup_environment()