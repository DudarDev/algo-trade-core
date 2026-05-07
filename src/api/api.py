import logging
import asyncio
from fastapi import FastAPI

from main import CryptoBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

app = FastAPI(title="Quantum Scalper API", version="1.0")

bot = CryptoBot()
bot_task = None

@app.on_event("startup")
async def startup_event():
    """Виконується при запуску FastAPI сервера."""
    logger.info("🚀 Підготовка бота до роботи (Rehydration)...")
    await bot.setup()

@app.on_event("shutdown")
async def shutdown_event():
    """Виконується при вимкненні FastAPI сервера."""
    global bot_task
    if bot_task and not bot_task.done():
        bot_task.cancel()
    await bot.cleanup()

@app.post("/api/v1/bot/start")
async def start_bot():
    """Ендпоінт для запуску бота."""
    global bot_task
    if bot_task and not bot_task.done():
        return {"status": "error", "message": "Бот вже працює! 🤖"}
    
    bot_task = asyncio.create_task(bot.start())
    return {"status": "success", "message": "Бот успішно запущений! 🟢"}

@app.post("/api/v1/bot/stop")
async def stop_bot():
    """Ендпоінт для зупинки бота."""
    global bot_task
    if bot_task and not bot_task.done():
        bot_task.cancel()
        bot_task = None
        return {"status": "success", "message": "Процес зупинки бота ініційовано... 🛑"}
    
    return {"status": "error", "message": "Бот наразі не працює."}

@app.get("/api/v1/bot/status")
async def get_status():
    """Ендпоінт для отримання статистики (для Django панелі)."""
    is_running = bot_task is not None and not bot_task.done()
    balance = await bot.trader.get_balance()
    open_positions_count = len(bot.trader.positions)
    active_symbols = list(bot.trader.positions.keys())
    
    return {
        "status": "online" if is_running else "offline",
        "balance": round(balance, 2),
        "open_positions_count": open_positions_count,
        "active_symbols": active_symbols
    }
