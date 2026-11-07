import logging
from typing import List
import asyncio

from src.engine.infrastructure.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(self, exchange_manager: ExchangeManager):
        self.exchange_manager = exchange_manager
        
        # Використовуємо вже готовий та налаштований публічний клієнт з ExchangeManager
        self.public_exchange = self.exchange_manager.public_exchange
        
        self.stablecoins = {'USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'USD', 'FDUSD', 'USDE', 'USDP'}
        self.priority_pairs = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT',
            'XRP/USDT', 'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT',
            'LINK/USDT', 'NEAR/USDT', 'SUI/USDT', 'APT/USDT',
            'DOT/USDT', 'ARB/USDT', 'OP/USDT', 'TIA/USDT',
            'INJ/USDT', 'BCH/USDT', 'LTC/USDT', 'UNI/USDT'
        ]
        
        # Токенізовані акції та синтетичні ETF, які заборонено торгувати
        self.synthetic_stocks = {
            'SOXLB', 'SOXSB', 'KORUB', 'TQQQB', 'SPCXB', 'TSLAB', 'INTCB', 'SNDKB', 'MUB',
            'NVDB', 'AAPLB', 'AMZNB', 'MSFTB', 'GOOGB', 'METAB', 'COINB', 'PLTRB'
        }

    def is_valid_crypto_symbol(self, symbol: str) -> bool:
        """Відсікає плечові токени (UP/DOWN/BULL/BEAR/3X), токенізовані акції та невалідні символи."""
        if not symbol.endswith('/USDT'):
            return False
        base = symbol.split('/')[0].upper()
        
        # 1. Тільки валідні латинські символи (відсікає ієрогліфи та кракозябри на зразок '牛来')
        if not base.isascii() or not base.isalnum():
            return False
            
        # 2. Не стейблкоїн
        if base in self.stablecoins:
            return False
            
        # 3. Відсікаємо плечові токени (Leveraged Tokens)
        leveraged_suffixes = ('UP', 'DOWN', 'BULL', 'BEAR', '2L', '2S', '3L', '3S')
        for suf in leveraged_suffixes:
            if base.endswith(suf) and len(base) > len(suf):
                return False
                
        # 4. Токенізовані акції та синтетичні біржові ETF
        if base in self.synthetic_stocks:
            return False

        return True

    async def get_top_volatile_pairs(self, limit: int = 20, min_volume: float = 10_000_000.0) -> List[str]:
        """Шукає пари з найбільшою волатильністю (через Public API), гарантовано додаючи топ-ліквідні активи."""
        for attempt in range(3):
            try:
                logger.info("🔍 [Scanner] Сканування ринку та відбір ліквідних пар (Public API)...")
                
                tickers = await self.public_exchange.fetch_tickers()
                pairs_data = []
                
                for symbol, data in tickers.items():
                    if not self.is_valid_crypto_symbol(symbol):
                        continue
                    
                    quote_vol = data.get('quoteVolume')
                    if quote_vol is None or float(quote_vol) < min_volume:
                        continue

                    # Фільтр спреду: відсікаємо низьколіквідні пастки з широким спредом (>0.25%)
                    bid = data.get('bid')
                    ask = data.get('ask')
                    if bid is not None and ask is not None:
                        try:
                            f_bid, f_ask = float(bid), float(ask)
                            if f_bid > 0 and ((f_ask - f_bid) / f_bid) > 0.0025:
                                continue
                        except (ValueError, TypeError):
                            pass
                    
                    change_pct = abs(data.get('percentage') or 0.0)
                    pairs_data.append({'symbol': symbol, 'change': change_pct})
                
                # Сортуємо альткоїни за волатильністю
                sorted_pairs = sorted(pairs_data, key=lambda x: x['change'], reverse=True)
                volatile_candidates = [p['symbol'] for p in sorted_pairs]
                
                # Формуємо підсумковий список: спочатку пріоритетні монети, потім топ-волатильні
                final_pairs = []
                for p in self.priority_pairs:
                    if p in tickers and p not in final_pairs:
                        final_pairs.append(p)
                
                for p in volatile_candidates:
                    if p not in final_pairs and len(final_pairs) < limit:
                        final_pairs.append(p)
                
                if not final_pairs:
                    logger.warning("⚠️ Не знайдено пар, що відповідають критеріям об'єму.")
                    return []
                
                logger.info(f"🔥 Знайдено активні пари для аналізу ({len(final_pairs)}): {final_pairs}")
                return final_pairs

            except Exception as e:
                logger.error(f"❌ Помилка сканера (спроба {attempt+1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(5)
                else:
                    logger.error("🛑 Вичерпано спроби сканування.")
                    return []
        return []
