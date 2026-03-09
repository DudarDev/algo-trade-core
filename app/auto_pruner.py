import sqlite3
import pandas as pd
import logging
import os

logger = logging.getLogger("AutoPruner")

class AutoPruner:
    def __init__(self):
        self.db_path = self._find_database()
        self.blacklist = set()

    def _find_database(self) -> str:
        """Розумний пошук бази даних у Docker-контейнері."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        possible_dbs = []
        for root, dirs, files in os.walk(base_dir):
            if 'venv' in root or '.git' in root or '__pycache__' in root:
                continue
            for file in files:
                if file.endswith(('.sqlite3', '.db')):
                    possible_dbs.append(os.path.join(root, file))
        
        for db in possible_dbs:
            try:
                conn = sqlite3.connect(db)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [t[0] for t in cursor.fetchall()]
                conn.close()
                
                if any('trade' in t.lower() for t in tables):
                    logger.info(f"✅ AutoPruner: Підключено до БД -> {db}")
                    return db
            except Exception:
                continue
                
        logger.warning("⚠️ AutoPruner: БД з історією угод не знайдено!")
        return None

    def update_blacklist(self, min_trades: int = 5, min_win_rate: float = 35.0) -> set:
        """Аналізує БД і банить монети з низьким Win Rate."""
        if not self.db_path:
            return self.blacklist

        try:
            conn = sqlite3.connect(self.db_path)
            tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
            trade_tables = [t for t in tables['name'].tolist() if 'trade' in t.lower()]
            
            if not trade_tables:
                conn.close()
                return self.blacklist
                
            table_name = trade_tables[-1]
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            conn.close()

            if df.empty:
                return self.blacklist

            cols = df.columns.str.lower()
            sym_col = df.columns[cols.str.contains('symbol')][0] if any(cols.str.contains('symbol')) else None
            pnl_col = df.columns[cols.str.contains('profit|pnl')][0] if any(cols.str.contains('profit|pnl')) else None
            action_col = df.columns[cols.str.contains('action|side|type')][0] if any(cols.str.contains('action|side|type')) else None

            if not sym_col or not pnl_col:
                return self.blacklist

            if action_col:
                df = df[df[action_col].str.upper().isin(['SELL', 'CLOSE'])]

            # 🔥 ФІКС ПАРСИНГУ: Очищаємо PnL від '%', 'USDT' та іншого сміття
            df['pnl_clean'] = df[pnl_col].astype(str).str.replace(r'[^\d\.-]', '', regex=True)
            df['pnl_clean'] = pd.to_numeric(df['pnl_clean'], errors='coerce').fillna(0)

            stats = df.groupby(sym_col).agg(
                total_trades=(sym_col, 'count'),
                wins=('pnl_clean', lambda x: (x > 0).sum()),
            )
            
            stats['win_rate'] = (stats['wins'] / stats['total_trades']) * 100

            # Захист від помилкового масового бану (якщо всі монети показують 0%)
            if (stats['win_rate'] == 0).all() and len(stats) > 1:
                logger.error("⚠️ AutoPruner: Захисний механізм. Всі монети 0%, скасовую бан.")
                return self.blacklist

            # Формуємо чорний список
            trash = stats[(stats['total_trades'] >= min_trades) & (stats['win_rate'] < min_win_rate)]
            new_blacklist = set(trash.index.tolist())

            if new_blacklist != self.blacklist:
                logger.info(f"🧹 AutoPruner: Чорний список оновлено (Win Rate < {min_win_rate}%): {list(new_blacklist)}")
                self.blacklist = new_blacklist
            else:
                logger.info(f"✨ AutoPruner: Чорний список без змін. Поточний бан: {list(self.blacklist)}")

            return self.blacklist

        except Exception as e:
            logger.error(f"❌ AutoPruner Error: {e}")
            return self.blacklist