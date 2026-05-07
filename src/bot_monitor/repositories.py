import sqlite3
import os
from typing import List, Dict, Any
from django.conf import settings

class BotDataRepository:
    def __init__(self):
        # Використовуємо BASE_DIR з налаштувань Django, щоб шлях завжди був правильним
        self.db_path = os.path.join(settings.BASE_DIR, 'data', 'bot_data.db')

    def _execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def get_open_positions(self) -> List[Dict[str, Any]]:
        # Переконайся, що ці колонки існують у твоїй таблиці open_positions
        query = "SELECT symbol, entry_price, current_conf, amount, stop_loss, take_profit FROM open_positions"
        rows = self._execute_query(query)
        return [dict(row) for row in rows]

    def get_pruned_blacklist(self) -> List[str]:
        # Логіка AutoPruner
        query = "SELECT symbol FROM trade_history GROUP BY symbol HAVING (SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(id)) < 35.0 AND COUNT(id) >= 5"
        rows = self._execute_query(query)
        return [row['symbol'] for row in rows]