# --- НАЛАШТУВАННЯ РИЗИКУ ---
TAKE_PROFIT_PCT = 0.007   # 0.7% (Ціль для фіксованого прибутку)
STOP_LOSS_PCT = 0.015     # 1.5% (Максимальний збиток)
AI_CONFIDENCE = 0.70      # 70% (Поріг впевненості AI для входу)

# --- TRAILING STOP (Ковзний стоп) ---
USE_TRAILING_STOP = True  # Включити розумний вихід?
TRAILING_START_PCT = 0.005 # 0.5% (При якому профіті включається трейлінг)
TRAILING_DROP_PCT = 0.002  # 0.2% (На скільки ціна може впасти від піку перед продажем)

# --- НАЛАШТУВАННЯ ТОРГІВЛІ ---
TIMEFRAME = '5m'          # Таймфрейм свічок
TRADE_AMOUNT = 100        # Ставка на одну угоду (USDT)
MAX_POSITIONS = 10        # Скільки монет можна тримати одночасно

# --- СПИСОК ПАР (Топ-10 Ліквідних) ---
PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'LINK/USDT', 'LTC/USDT'
]