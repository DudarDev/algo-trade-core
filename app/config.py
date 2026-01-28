from dataclasses import dataclass, field
from typing import List

@dataclass(frozen=True)
class TradingConfig:
    # --- MARKET SETTINGS ---
    TIMEFRAME: str = '5m'
    
    # Видаляємо PAXG та неліквід. Залишаємо те, де AI реально бачить закономірності
    PAIRS: List[str] = field(default_factory=lambda: [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 
        'XRP/USDT', 'ADA/USDT', 'DOT/USDT', 'LINK/USDT'
    ])
    
    # Токсичні активи, які Scanner може випадково підсунути
    BLACKLIST: List[str] = field(default_factory=lambda: [
        'PAXG/USDT', 'USDC/USDT', 'FDUSD/USDT', 'TUSD/USDT', 'PEPE/USDT', 'DOGE/USDT'
    ])

    # --- RISK MANAGEMENT (Жорсткий контроль) ---
    # Збільшуємо SL, щоб не вибивало випадковим шумом, але зменшуємо об'єм позиції
    STOP_LOSS_PCT: float = 0.025   # 2.5% - Даємо ціні трохи "подихати"
    TAKE_PROFIT_PCT: float = 0.05  # 5.0% - Націлюємося на серйозніші рухи
    
    # Position Sizing
    MAX_POSITIONS: int = 3
    # При депо ~380 USDT це буде ~$76 на угоду. Безпечно.
    POSITION_SIZE_FRACTION: float = 0.20 

    # --- TRAILING STOP (Адаптований під логі) ---
    USE_TRAILING: bool = True
    # Вмикаємо трейлінг пізніше (після 1.5%), щоб не різати прибуток на самому початку
    TRAILING_ACTIVATION: float = 0.015  # 1.5%
    # Відступ робимо більшим, щоб не виходити на мікро-відкатах
    TRAILING_DISTANCE: float = 0.007    # 0.7% drop from peak

    # --- AI BRAIN ---
    # Твій поріг 0.60 дає багато "шумних" сигналів. Піднімаємо якість.
    MODEL_THRESHOLD: float = 0.68
    EMA_PERIOD: int = 200
    
    # Технічний параметр для стабільності CCXT
    RETRY_LIMIT: int = 5
    TIMEOUT: int = 30000