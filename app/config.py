import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

class Config:
    PROJECT_NAME = "AlgoTradeCore_Pro"
    VERSION = "8.2.0_Wide_Stops"
    
    BASE_DIR = Path(__file__).resolve().parent.parent
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    EXCHANGES: List[str] = ['binanceus', 'kraken', 'coinbase']
    EXCHANGE_KEYS: Dict[str, Dict[str, str]] = {
        'binanceus': {'apiKey': os.getenv("BINANCE_API_KEY", ""), 'secret': os.getenv("BINANCE_API_SECRET", "")},
        'kraken': {'apiKey': os.getenv("KRAKEN_API_KEY", ""), 'secret': os.getenv("KRAKEN_API_SECRET", "")},
        'coinbase': {'apiKey': os.getenv("COINBASE_API_KEY", ""), 'secret': os.getenv("COINBASE_API_SECRET", "")}
    }
    ARBITRAGE_MIN_SPREAD_PCT = 1.5
    IS_PAPER_TRADING = os.getenv("IS_PAPER_TRADING", "True").lower() == "true"
    
    SYMBOLS: List[str] = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'SHIB/USDT', 'DOGE/USDT', 'XRP/USDT', 'LTC/USDT']
    BLACKLIST: List[str] = ['HYPE/USDT', 'PAXG/USDT', 'USDC/USDT', 'FDUSD/USDT', 'PUMP/USDT', 'ZEC/USDT', 'HBAR/USDT', 'PEPE/USDT']
    
    # 🔥 РІШЕННЯ ПРОБЛЕМИ: Переходимо на 5 хвилин для надійності
    TIMEFRAME = "5m" 
    
    MAX_OPEN_POSITIONS = 3      
    USDT_PER_TRADE = 50.0       
    POSITION_SIZE_FRACTION = 0.15
    
    # 🔥 РІШЕННЯ ПРОБЛЕМИ: Ширші стопи, щоб не вибивало ринковим шумом
    STOP_LOSS_ATR_MULT = 3.5    
    TAKE_PROFIT_ATR_MULT = 6.0  
    
    DATA_DIR = BASE_DIR / "data"
    MODEL_DIR = DATA_DIR / "models"
    LOG_DIR = BASE_DIR / "logs"
    
    AI_CONFIDENCE_THRESHOLD = 0.62  
    ADX_THRESHOLD = 20 

    MIN_TRAINING_SAMPLES = 500      
    TRAINING_LOOKBACK = 1000 
    
    @classmethod
    def setup_environment(cls):
        for path in [cls.MODEL_DIR, cls.LOG_DIR, cls.DATA_DIR]:
            path.mkdir(parents=True, exist_ok=True)

Config.setup_environment()