from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Для прикладу беремо SQLite, але в продакшені це буде тягнутися з settings.DATABASE_URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./data_storage/bot_data.db"

# connect_args={"check_same_thread": False} потрібен тільки для SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency для отримання сесії БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()