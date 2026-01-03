import sqlite3
import logging
import os


class DatabaseManager:
    def __init__(self, db_file="data/bot_data.db"):
        # Переконуємось, що папка data існує
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Таблиця для угод
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT, -- BUY або SELL
                price REAL,
                amount REAL,
                cost REAL,
                pnl REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        # Таблиця для стану гаманця (щоб пам'ятати баланс)
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wallet (
                id INTEGER PRIMARY KEY,
                usdt_balance REAL
            )
        """
        )
        self.conn.commit()

    def log_trade(self, symbol, side, price, amount, cost, pnl=0):
        try:
            self.cursor.execute(
                """
                INSERT INTO trades (symbol, side, price, amount, cost, pnl)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (symbol, side, price, amount, cost, pnl),
            )
            self.conn.commit()
        except Exception as e:
            logging.error(f"DB Error (Trade): {e}")

    def save_balance(self, balance):
        try:
            # Оновлюємо єдиний запис з ID=1
            self.cursor.execute(
                "INSERT OR REPLACE INTO wallet (id, usdt_balance) VALUES (1, ?)",
                (balance,),
            )
            self.conn.commit()
        except Exception as e:
            logging.error(f"DB Error (Balance): {e}")

    def load_balance(self, default=1000.0):
        try:
            self.cursor.execute("SELECT usdt_balance FROM wallet WHERE id=1")
            row = self.cursor.fetchone()
            if row:
                return row[0]
            else:
                return default
        except:
            return default
