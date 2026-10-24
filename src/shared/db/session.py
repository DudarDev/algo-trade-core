import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = BASE_DIR / "data_storage" / "bot_data.db"

# Динамічно читаємо URL бази даних
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # PostgreSQL не потребує check_same_thread
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def migrate_schema(target_engine):
    """
    Автоматично додає відсутні стовпці у наявні таблиці SQLite/PostgreSQL
    без руйнування існуючих даних (Feature Store & Trade Journaling).
    """
    from sqlalchemy import inspect, text
    try:
        inspector = inspect(target_engine)
        existing_tables = inspector.get_table_names()

        columns_to_add = {
            "trades": [
                ("exit_reason", "VARCHAR(50) DEFAULT 'UNKNOWN'"),
                ("regime", "VARCHAR(30) DEFAULT 'CHOPPY_FLAT'"),
                ("ai_confidence", "FLOAT DEFAULT 0.0"),
                ("target_label", "INTEGER DEFAULT 0"),
                ("features_json", "TEXT DEFAULT '{}'"),
            ],
            "active_positions": [
                ("regime", "VARCHAR(30) DEFAULT 'CHOPPY_FLAT'"),
                ("ai_confidence", "FLOAT DEFAULT 0.0"),
                ("features_json", "TEXT DEFAULT '{}'"),
                ("partial_tp_hit", "INTEGER DEFAULT 0"),
            ]
        }

        with target_engine.connect() as conn:
            for table_name, columns in columns_to_add.items():
                if table_name in existing_tables:
                    existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
                    for col_name, col_type in columns:
                        if col_name not in existing_cols:
                            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"⚠️ Помилка автоматичної міграції схеми: {e}")

def init_db():
    """Створює всі необхідні таблиці в БД, якщо вони ще не існують, та оновлює схему."""
    from src.shared.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    migrate_schema(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
