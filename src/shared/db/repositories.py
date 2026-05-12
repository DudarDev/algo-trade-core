import logging
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from src.shared.db.models import ActivePosition, Wallet, Trade
from src.shared.config import settings

logger = logging.getLogger(__name__)

# Ініціалізуємо фабрику сесій
# Переконайся, що DATABASE_URL імпортується або береться з settings правильно
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

@contextmanager
def get_session():
    """Контекстний менеджер для безпечного керування сесіями БД у різних потоках"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Помилка транзакції БД: {e}")
        raise
    finally:
        session.close()

class DatabaseRepository:
    """Репозиторій для роботи з БД. Тепер потокобезпечний (Thread-Safe)!"""
    
    def save_position(self, position: ActivePosition):
        with get_session() as session:
            session.merge(position)

    def get_position(self, symbol: str) -> ActivePosition:
        # Для читання теж відкриваємо коротку сесію
        with get_session() as session:
            # Використовуємо .first() і повертаємо об'єкт (він буде від'єднаний від сесії після with, 
            # але для читання даних у пам'ять цього достатньо)
            pos = session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()
            if pos:
                # Змушуємо SQLAlchemy завантажити дані в пам'ять перед закриттям сесії
                session.expunge(pos)
            return pos

    def delete_position(self, symbol: str):
        with get_session() as session:
            position = session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()
            if position:
                session.delete(position)

    def update_position_high(self, symbol: str, highest_price: float):
        with get_session() as session:
            position = session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()
            if position:
                position.highest_price = highest_price
                # commit відбудеться автоматично при виході з блоку with

    def save_balance(self, balance: float):
        with get_session() as session:
            wallet = session.query(Wallet).first()
            if not wallet:
                wallet = Wallet(usdt_balance=balance)
                session.add(wallet)
            else:
                wallet.usdt_balance = balance

    def save_trade(self, trade: Trade):
        with get_session() as session:
            session.add(trade)
            
    def get_all_active_positions(self):
        with get_session() as session:
            positions = session.query(ActivePosition).all()
            for pos in positions:
                session.expunge(pos)
            return positions