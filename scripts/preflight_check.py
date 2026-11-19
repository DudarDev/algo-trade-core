#!/usr/bin/env python3
"""
Pre-flight check перед запуском algo-bot у режимі LIVE.
Перевіряє: валідність ключів, права API (заборона Withdrawals, IP-фільтр),
баланси USDT/BNB та відсутність «завислих» відкритих ордерів.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
import ccxt.async_support as ccxt

load_dotenv()

MIN_USDT_REQUIRED = 40.0   # Мінімум для мікро-лотного тесту на $50
MIN_BNB_USDT_VALUE = 2.0   # Мінімум BNB для активації 25% знижки на комісії


async def run_preflight() -> int:
    trading_mode = os.getenv("TRADING_MODE", "PAPER").strip().upper()
    if trading_mode != "LIVE":
        print(f"⚪ [PRE-FLIGHT] TRADING_MODE={trading_mode}. Перевірка Live API пропущена.")
        return 0

    api_key = (os.getenv("BINANCE_API_KEY") or "").strip()
    api_secret = (os.getenv("BINANCE_API_SECRET") or os.getenv("BINANCE_SECRET_KEY") or "").strip()

    if not api_key or not api_secret:
        print("❌ [FAIL] BINANCE_API_KEY або BINANCE_API_SECRET (чи BINANCE_SECRET_KEY) не задані в .env")
        return 2

    exchange = ccxt.binance({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
        "options": {
            "defaultType": "spot",
            "warnOnFetchOpenOrdersWithoutSymbol": False,
        },
    })

    has_critical_error = False
    print("🚀 Запуск Pre-Flight перевірки Binance Live API...\n")

    try:
        # 1. Перевірка прав API-ключа та безпеки
        restrictions = await exchange.sapi_get_account_apirestrictions()
        ip_restrict = restrictions.get("ipRestrict", False)
        can_spot = restrictions.get("enableSpotAndMarginTrading", False)
        can_withdraw = restrictions.get("enableWithdrawals", True)
        can_futures = restrictions.get("enableFutures", False)

        print("🔐 Права API-ключа:")
        print(f"   • Spot Trading: {'✅ OK' if can_spot else '❌ ВИМКНЕНО'}")
        print(f"   • Futures:      {'🟢 УВІМКНЕНО' if can_futures else '⚪ ВИМКНЕНО (тільки Spot)'}")
        print(f"   • IP Restrict:  {'✅ OK' if ip_restrict else '⚠️ НЕ ПРИВʼЯЗАНО ДО IP'}")
        print(f"   • Withdrawals:  {'✅ ВИМКНЕНО (безпечно)' if not can_withdraw else '🚨 УВІМКНЕНО (НЕБЕЗПЕЧНО!)'}")

        if not can_spot:
            print("   ❌ [BLOCKER] Увімкніть 'Enable Spot & Margin Trading' на Binance.")
            has_critical_error = True
        if can_withdraw:
            print("   ❌ [BLOCKER] Вимкніть 'Enable Withdrawals' на API-ключі перед запуском!")
            has_critical_error = True

        # 2. Перевірка балансів USDT та BNB
        balance = await exchange.fetch_balance()
        free_usdt = float(balance.get("USDT", {}).get("free", 0.0))
        free_bnb = float(balance.get("BNB", {}).get("free", 0.0))

        bnb_ticker = await exchange.fetch_ticker("BNB/USDT")
        bnb_price = float(bnb_ticker["last"])
        bnb_usdt_val = free_bnb * bnb_price

        print("\n💰 Баланси (Spot Free):")
        print(f"   • USDT: ${free_usdt:.2f} (мін. поріг: ${MIN_USDT_REQUIRED:.2f})")
        print(f"   • BNB:  {free_bnb:.5f} (~${bnb_usdt_val:.2f}, мін. поріг: ${MIN_BNB_USDT_VALUE:.2f})")

        if free_usdt < MIN_USDT_REQUIRED:
            print(f"   ❌ [BLOCKER] Недостатньо вільного USDT (${free_usdt:.2f} < ${MIN_USDT_REQUIRED:.2f}).")
            has_critical_error = True
        if bnb_usdt_val < MIN_BNB_USDT_VALUE:
            print(f"   ⚠️ [WARN] Мало BNB (~${bnb_usdt_val:.2f}). Знижка 25% може не спрацювати до першого авто-поповнення.")

        # 3. Перевірка відкритих ордерів на Spot
        open_orders = await exchange.fetch_open_orders()
        print(f"\n📋 Відкриті ордери на Spot: {len(open_orders)}")
        if open_orders:
            for order in open_orders:
                print(f"   ⚠️ {order['symbol']} | {order['side'].upper()} | {order['amount']} @ {order['price']} (ID: {order['id']})")
            print("   ❌ [BLOCKER] Скасуйте старі ордери перед стартом бота, щоб уникнути конфлікту маржі.")
            has_critical_error = True
        else:
            print("   ✅ Чисто (0 відкритих ордерів).")

    except ccxt.AuthenticationError as e:
        print(f"❌ [AUTH FAIL] Невалідний ключ, секрет або IP-адреса не у білому списку:\n   {e}")
        return 2
    except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as e:
        print(f"⚠️ [NETWORK ERROR] Тимчасовий збій зв'язку з Binance: {e}")
        return 1
    except Exception as e:
        print(f"❌ [ERROR] Помилка під час перевірки: {e}")
        return 2
    finally:
        await exchange.close()

    print("\n" + "=" * 50)
    if has_critical_error:
        print("🛑 VERDICT: NO-GO. Виправте блокери вище перед запуском LIVE.")
        return 2

    print("🟢 VERDICT: GO! Система готова до безпечного запуску LIVE.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run_preflight()))
