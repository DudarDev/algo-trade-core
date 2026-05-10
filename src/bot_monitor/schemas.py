from datetime import datetime
from ninja import Schema

class WalletSchema(Schema):
    usdt_balance: float

class TradeSchema(Schema):
    id: int
    symbol: str
    side: str
    price: float
    amount: float
    pnl: float
    timestamp: datetime