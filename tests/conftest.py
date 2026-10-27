import os
import sys
from pathlib import Path
import joblib
import numpy as np

# Корінь проєкту
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

# Гарантуємо створення data_storage та базових моделей для чистого CI/CD середовища
data_dir = ROOT_DIR / "data_storage"
models_dir = data_dir / "models"
models_dir.mkdir(parents=True, exist_ok=True)

rf_path = models_dir / "global_rf_v4.pkl"
if not rf_path.exists():
    from sklearn.ensemble import RandomForestClassifier
    from src.infrastructure.ai.feature_engineer import get_feature_columns
    cols = get_feature_columns()
    X = np.random.rand(10, len(cols))
    y = np.random.randint(0, 2, size=10)
    dummy_rf = RandomForestClassifier(n_estimators=2, random_state=42)
    dummy_rf.fit(X, y)
    joblib.dump(dummy_rf, rf_path)

lgbm_path = models_dir / "global_lgbm_v1.pkl"
if not lgbm_path.exists():
    import lightgbm as lgb
    from src.infrastructure.ai.feature_engineer import get_feature_columns
    cols = get_feature_columns()
    X = np.random.rand(10, len(cols))
    y = np.random.randint(0, 2, size=10)
    dummy_lgbm = lgb.LGBMClassifier(n_estimators=2, random_state=42, verbose=-1)
    dummy_lgbm.fit(X, y)
    joblib.dump(dummy_lgbm, lgbm_path)

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
