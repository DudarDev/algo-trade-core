{
    "exchange": {
        "name": "binance",
        "symbol": "BTC/USDT",
        "timeframe": "1m"
    },
    "strategy": {
        "name": "RSI",
        "rsi_period": 14,
        "buy_level": 45,
        "sell_level": 55
    },
    "risk_management": {
        "start_balance": 1000,
        "min_trade_usdt": 10
    },
    "system": {
        "check_interval_seconds": 5,
        "log_file": "data/trades_history.csv",
        "chart_file": "data/trading_chart.png"
    }
}