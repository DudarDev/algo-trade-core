import os
import sys
from pathlib import Path

# Корінь проєкту
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

# Гарантуємо створення data_storage для чистого CI/CD середовища
data_dir = ROOT_DIR / "data_storage"
data_dir.mkdir(parents=True, exist_ok=True)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_panel.settings')
import django
django.setup()

# Ініціалізуємо схему таблиць бази даних та тестові фікстури для CI
from src.shared.db.session import init_db, engine
from sqlalchemy import text
init_db()

with engine.connect() as conn:
    conn.execute(text("INSERT OR IGNORE INTO bot_config (id, status) VALUES (1, 'active')"))
    conn.execute(text("INSERT OR IGNORE INTO wallet (id, usdt_balance) VALUES (1, 1000.0)"))
    conn.commit()
