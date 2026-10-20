import logging
from typing import List, Dict, Any
from django.db import connection

logger = logging.getLogger(__name__)

class BotDataRepository:
    def _dictfetchall(self, cursor):
        """Перетворює результати запиту у список словників."""
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

    def _execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return self._dictfetchall(cursor)
        except Exception as e:
            logger.error(f"Database repository error: {e}")
            return []

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Отримуємо активні позиції відповідно до схеми в models.py."""
        query = """
            SELECT symbol, entry_price, amount, cost, highest_price, opened_at 
            FROM active_positions
        """
        return self._execute_query(query)

    def get_pruned_blacklist(self) -> List[str]:
        """Логіка AutoPruner: монети з вінрейтом нижче 35% при мінімум 5 угодах."""
        query = """
            SELECT symbol FROM trades 
            GROUP BY symbol 
            HAVING (SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(id)) < 35.0 
            AND COUNT(id) >= 5
        """
        rows = self._execute_query(query)
        return [row['symbol'] for row in rows]