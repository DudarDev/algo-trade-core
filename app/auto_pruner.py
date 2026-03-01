import sqlite3
import pandas as pd
import logging
import os

logger = logging.getLogger("AutoPruner")

class AutoPruner:
    def __init__(self):
        # Шукаємо базу даних там, де вона може бути в Docker
        db_paths = ['db.sqlite3', 'bot_data/db.sqlite3', 'data/db.sqlite3']
        self.db_path = None
        for path in db_paths:
            if os.path.exists(path):
                self.db_path = path
                break
        
        self.blacklist = set()

    def update_blacklist(self, min_trades: int = 5, min_win_rate: float = 35.0) -> set:
        """
        Аналізує базу даних і формує список 'сміттєвих' монет.
        min_trades: мінімальна кількість угод для оцінки.
        min_win_rate: поріг відсотка успішних угод.
        """
        if not self.db_path:
            logger.warning("⚠️ Базу даних для AutoPruner не знайдено.")
            return self.blacklist

        try:
            conn = sqlite3.connect(self.db_path)
            
            # Шукаємо таблицю з історією угод (Django ORM зазвичай створює таблиці зі словом trade)
            tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
            trade_tables = [t for t in tables['name'].tolist() if 'trade' in t.lower()]
            
            if not trade_tables:
                conn.close()
                return self.blacklist
                
            table_name = trade_tables[-1] # Беремо знайдену таблицю
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            conn.close()

            if df.empty:
                return self.blacklist

            # Універсальний пошук колонок (на випадок змін у БД)
            cols = df.columns.str.lower()
            sym_col = df.columns[cols.str.contains('symbol')][0] if any(cols.str.contains('symbol')) else None
            pnl_col = df.columns[cols.str.contains('profit|pnl')][0] if any(cols.str.contains('profit|pnl')) else None
            action_col = df.columns[cols.str.contains('action|side|type')][0] if any(cols.str.contains('action|side|type')) else None

            if not sym_col or not pnl_col:
                return self.blacklist

            # Залишаємо тільки закриті угоди (SELL)
            if action_col:
                df = df[df[action_col].str.upper().isin(['SELL', 'CLOSE'])]

            # Рахуємо Win Rate
            df[pnl_col] = pd.to_numeric(df[pnl_col], errors='coerce')
            stats = df.groupby(sym_col).agg(
                total_trades=(sym_col, 'count'),
                wins=(pnl_col, lambda x: (x > 0).sum()),
            )
            
            stats['win_rate'] = (stats['wins'] / stats['total_trades']) * 100

            # Визначаємо "сміттєві" монети
            trash = stats[(stats['total_trades'] >= min_trades) & (stats['win_rate'] < min_win_rate)]
            new_blacklist = set(trash.index.tolist())

            if new_blacklist != self.blacklist:
                logger.info(f"🧹 AutoPruner: Чорний список оновлено (Win Rate < {min_win_rate}%): {list(new_blacklist)}")
                self.blacklist = new_blacklist

            return self.blacklist

        except Exception as e:
            logger.error(f"❌ AutoPruner Error: {e}")
            return self.blacklist