import pytest
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from src.shared.db.models import Base
from src.shared.db.session import migrate_schema
from src.shared.db.repositories import TradingRepository

@pytest.fixture
def memory_db_repo(tmp_path):
    db_file = tmp_path / "test_repo.db"
    db_url = f"sqlite:///{db_file}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    migrate_schema(test_engine)
    
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    with patch('src.shared.db.repositories.SessionLocal', TestSessionLocal), \
         patch('src.shared.db.repositories.init_db', lambda: None):
        repo = TradingRepository()
        yield repo

def test_wallet_balance_lifecycle(memory_db_repo):
    # Initial balance creation
    bal = memory_db_repo.load_balance(default_balance=1500.0)
    assert bal == 1500.0

    # Save and reload
    memory_db_repo.save_balance(1420.50)
    reloaded = memory_db_repo.load_balance()
    assert reloaded == 1420.50

def test_position_crud_and_feature_store(memory_db_repo):
    # 1. Save Position
    memory_db_repo.save_position(
        symbol="BTC/USDT",
        amount=0.01,
        entry_price=50000.0,
        highest_price=50000.0,
        cost=500.0,
        regime="BULL_MARKET",
        ai_confidence=0.72,
        features_json='{"RSI": 0.55}'
    )

    # 2. Get Position
    pos = memory_db_repo.get_position("BTC/USDT")
    assert pos is not None
    assert pos.symbol == "BTC/USDT"
    assert pos.entry_price == 50000.0
    assert pos.regime == "BULL_MARKET"
    assert pos.ai_confidence == 0.72
    assert '{"RSI": 0.55}' == pos.features_json

    # 3. Update Position High
    memory_db_repo.update_position_high("BTC/USDT", 52000.0)
    updated_pos = memory_db_repo.get_position("BTC/USDT")
    assert updated_pos.highest_price == 52000.0

    # 4. Get all positions
    all_pos = memory_db_repo.get_all_positions()
    assert len(all_pos) == 1

    # 5. Delete Position
    memory_db_repo.delete_position("BTC/USDT")
    assert memory_db_repo.get_position("BTC/USDT") is None
    assert len(memory_db_repo.get_all_positions()) == 0

def test_trade_journaling_and_feedback_queries(memory_db_repo):
    # Log 2 trades
    memory_db_repo.log_trade(
        symbol="ETH/USDT",
        side="SELL",
        price=3100.0,
        amount=0.5,
        cost=1550.0,
        pnl=50.0,
        exit_reason="Take Profit",
        regime="BULL_MARKET",
        ai_confidence=0.68,
        target_label=1,
        features_json='{"ADX": 0.35}'
    )
    memory_db_repo.log_trade(
        symbol="SOL/USDT",
        side="SELL",
        price=120.0,
        amount=2.0,
        cost=240.0,
        pnl=-15.0,
        exit_reason="Stop Loss",
        regime="CHOPPY_FLAT",
        ai_confidence=0.33,
        target_label=0,
        features_json='{"ADX": 0.18}'
    )

    closed = memory_db_repo.get_closed_trades()
    assert len(closed) == 2
    assert closed[0].symbol == "SOL/USDT"  # Ordered by timestamp desc
    assert closed[0].target_label == 0
    assert closed[1].target_label == 1
    assert closed[1].pnl == 50.0
