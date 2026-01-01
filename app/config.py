# --- НАЛАШТУВАННЯ ТОРГІВЛІ ---
TIMEFRAME = '5m'
TRADE_AMOUNT = 100         # USDT на одну угоду
MAX_POSITIONS = 10         # Максимум угод одночасно

# --- РИЗИК-МЕНЕДЖМЕНТ ---
TAKE_PROFIT_PCT = 0.015    # 1.5% (Ціль)
STOP_LOSS_PCT = 0.010      # 1.0% (Стоп)

# --- TRAILING STOP (Розумний вихід) ---
USE_TRAILING_STOP = True
TRAILING_START_PCT = 0.005 # Активувати, коли прибуток > 0.5%
TRAILING_DROP_PCT = 0.003  # Продати, якщо ціна впала на 0.3% від піку

# --- СПИСОК ПАР (Стартовий, далі оновлюється сканером) ---
PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'LINK/USDT', 'LTC/USDT'
]
