from typing import List, Optional
from datetime import datetime, timezone
from .session import SessionLocal, init_db
from .models import ActivePosition, Wallet, Trade, DeltaNeutralPositionModel

class TradingRepository:
    def __init__(self, session=None):
        init_db()  # Автоматично перевіряємо та створюємо таблиці при старті репозиторію

    def load_balance(self, default_balance: float = 1000.0) -> float:
        with SessionLocal() as session:
            wallet = session.query(Wallet).first()
            if wallet:
                return wallet.usdt_balance
            
            # Якщо гаманця немає - створюємо!
            new_wallet = Wallet(usdt_balance=default_balance)
            session.add(new_wallet)
            session.commit()
            return default_balance

    def save_balance(self, balance: float) -> None:
        with SessionLocal() as session:
            wallet = session.query(Wallet).first()
            if wallet:
                wallet.usdt_balance = balance
            else:
                wallet = Wallet(usdt_balance=balance)
                session.add(wallet)
            session.commit()

    def get_all_positions(self) -> List[ActivePosition]:
        with SessionLocal() as session:
            return session.query(ActivePosition).all()

    def get_position(self, symbol: str) -> Optional[ActivePosition]:
        with SessionLocal() as session:
            return session.query(ActivePosition).filter_by(symbol=symbol).first()

    def save_position(
        self,
        symbol: str,
        amount: float,
        entry_price: float,
        highest_price: float,
        cost: float,
        regime: str = "CHOPPY_FLAT",
        ai_confidence: float = 0.0,
        features_json: str = "{}",
        partial_tp_hit: int = 0
    ) -> None:
        with SessionLocal() as session:
            pos = session.query(ActivePosition).filter_by(symbol=symbol).first()
            if pos:
                pos.amount = amount
                pos.entry_price = entry_price
                pos.highest_price = highest_price
                pos.cost = cost
                pos.regime = regime
                pos.ai_confidence = ai_confidence
                pos.features_json = features_json
                pos.partial_tp_hit = partial_tp_hit
            else:
                pos = ActivePosition(
                    symbol=symbol,
                    amount=amount,
                    entry_price=entry_price,
                    highest_price=highest_price,
                    cost=cost,
                    regime=regime,
                    ai_confidence=ai_confidence,
                    features_json=features_json,
                    partial_tp_hit=partial_tp_hit
                )
                session.add(pos)
            session.commit()

    def update_position_high(self, symbol: str, highest_price: float) -> None:
        with SessionLocal() as session:
            pos = session.query(ActivePosition).filter_by(symbol=symbol).first()
            if pos:
                pos.highest_price = highest_price
                session.commit()

    def delete_position(self, symbol: str) -> None:
        with SessionLocal() as session:
            session.query(ActivePosition).filter_by(symbol=symbol).delete()
            session.commit()

    def log_trade(
        self,
        symbol: str,
        side: str,
        price: float,
        amount: float,
        cost: float,
        pnl: float,
        exit_reason: str = "UNKNOWN",
        regime: str = "CHOPPY_FLAT",
        ai_confidence: float = 0.0,
        target_label: int = 0,
        features_json: str = "{}"
    ) -> None:
        with SessionLocal() as session:
            trade = Trade(
                symbol=symbol,
                side=side,
                price=price,
                amount=amount,
                cost=cost,
                pnl=pnl,
                exit_reason=exit_reason,
                regime=regime,
                ai_confidence=ai_confidence,
                target_label=target_label,
                features_json=features_json
            )
            session.add(trade)
            session.commit()

    def get_closed_trades(self, limit: Optional[int] = None) -> List[Trade]:
        with SessionLocal() as session:
            query = session.query(Trade).filter(Trade.side == "SELL").order_by(Trade.timestamp.desc(), Trade.id.desc())
            if limit:
                query = query.limit(limit)
            return query.all()

    # --- Delta-Neutral Cash & Carry Repository Methods ---

    def get_active_delta_neutral_positions(self) -> List[DeltaNeutralPositionModel]:
        with SessionLocal() as session:
            return session.query(DeltaNeutralPositionModel).filter_by(status="OPEN").all()

    def save_delta_neutral_position(self, pos_model: DeltaNeutralPositionModel) -> None:
        with SessionLocal() as session:
            existing = session.query(DeltaNeutralPositionModel).filter_by(id=pos_model.id).first()
            if existing:
                for col in DeltaNeutralPositionModel.__table__.columns:
                    setattr(existing, col.name, getattr(pos_model, col.name))
            else:
                session.add(pos_model)
            session.commit()

    def update_delta_neutral_funding(
        self,
        position_id: str,
        funding_payment: float,
        current_8h_rate: float,
        projected_apy: float
    ) -> Optional[DeltaNeutralPositionModel]:
        with SessionLocal() as session:
            pos = session.query(DeltaNeutralPositionModel).filter_by(id=position_id).first()
            if pos:
                pos.accrued_funding_usdt += funding_payment
                pos.funding_cycles_collected += 1
                pos.current_8h_rate = current_8h_rate
                pos.projected_apy = projected_apy
                pos.last_funding_time = datetime.now(timezone.utc)
                session.commit()
                session.refresh(pos)
                return pos
            return None

    def close_delta_neutral_position(self, position_id: str, close_reason: str) -> None:
        with SessionLocal() as session:
            pos = session.query(DeltaNeutralPositionModel).filter_by(id=position_id).first()
            if pos:
                pos.status = "CLOSED"
                pos.close_reason = close_reason
                session.commit()

