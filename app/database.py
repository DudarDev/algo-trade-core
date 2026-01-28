import sqlite3
import logging
import os
import json
from typing import Dict, Any

logger = logging.getLogger("Database")

class DatabaseManager:
    def __init__(self, db_file: str = "data/bot_data.db"):
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        # Вмикаємо повернення рядків як словників для зручності
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Створення структури БД з підтримкою персистентності позицій."""
        with self.conn:
            # 1. Журнал усіх угод
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    side TEXT,
                    price REAL,
                    amount REAL,
                    cost REAL,
                    pnl REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 2. Баланс гаманця
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS wallet (
                    id INTEGER PRIMARY KEY,
                    usdt_balance REAL
                )
            """)
            # 3. АКТИВНІ ПОЗИЦІЇ (Критично для виживання бота)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_positions (
                    symbol TEXT PRIMARY KEY,
                    amount REAL,
                    entry_price REAL,
                    highest_price REAL,
                    cost REAL,
                    opened_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

    # --- Керування позиціями ---

    def save_position(self, symbol: str, pos_data: Dict[str, Any]):
        """Зберігає відкриту позицію в БД."""
        try:
            with self.conn:
                self.cursor.execute("""
                    INSERT OR REPLACE INTO active_positions 
                    (symbol, amount, entry_price, highest_price, cost)
                    VALUES (?, ?, ?, ?, ?)
                """, (symbol, pos_data['amount'], pos_data['entry_price'], 
                      pos_data['highest_price'], pos_data['cost']))
        except Exception as e:
            logger.error(f"❌ DB Error (save_position): {e}")

    def update_position_high(self, symbol: str, highest_price: float):
        """Оновлює пікову ціну для трейлінгу."""
        try:
            with self.conn:
                self.cursor.execute(
                    "UPDATE active_positions SET highest_price = ? WHERE symbol = ?",
                    (highest_price, symbol)
                )
        except Exception as e:
            logger.error(f"❌ DB Error (update_high): {e}")

    def load_open_positions(self) -> Dict[str, Any]:
        """Завантажує всі відкриті позиції при старті бота."""
        positions = {}
        try:
            self.cursor.execute("SELECT * FROM active_positions")
            rows = self.cursor.fetchall()
            for row in rows:
                positions[row['symbol']] = {
                    "amount": row['amount'],
                    "entry_price": row['entry_price'],
                    "highest_price": row['highest_price'],
                    "cost": row['cost']
                }
            return positions
        except Exception as e:
            logger.error(f"❌ DB Error (load_positions): {e}")
            return {}

    def delete_position(self, symbol: str):
        """Видаляє позицію після продажу."""
        try:
            with self.conn:
                self.cursor.execute("DELETE FROM active_positions WHERE symbol = ?", (symbol,))
        except Exception as e:
            logger.error(f"❌ DB Error (delete_position): {e}")

    # --- Керування балансом та логами ---

    def log_trade(self, symbol, side, price, amount, cost, pnl=0):
        try:
            with self.conn:
                self.cursor.execute("""
                    INSERT INTO trades (symbol, side, price, amount, cost, pnl)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (symbol, side, price, amount, cost, pnl))
        except Exception as e:
            logger.error(f"❌ DB Error (log_trade): {e}")

    def save_balance(self, balance: float):
        try:
            with self.conn:
                self.cursor.execute(
                    "INSERT OR REPLACE INTO wallet (id, usdt_balance) VALUES (1, ?)",
                    (balance,)
                )
        except Exception as e:
            logger.error(f"❌ DB Error (save_balance): {e}")

    def load_balance(self, default: float = 1000.0) -> float:
        try:
            self.cursor.execute("SELECT usdt_balance FROM wallet WHERE id=1")
            row = self.cursor.fetchone()
            return row['usdt_balance'] if row else default
        except Exception as e:
            logger.error(f"❌ DB Error (load_balance): {e}")
            return default