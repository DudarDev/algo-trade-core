"""
Модуль щотижневого автоматичного завантаження свічок з Binance та перенавчання моделі Random Forest.
Забезпечує безперервну адаптацію штучного інтелекту до змінюваних режимів ринку.
"""

import os
import sys
import time
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple

import ccxt
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, roc_auc_score

# Корінь проєкту
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.shared.config import settings
from src.infrastructure.ai.feature_engineer import calculate_features, get_feature_columns
from src.infrastructure.ai.train_pipeline import create_triple_barrier_labels
from src.engine.infrastructure.telegram_notifier import TelegramNotifier

logger = logging.getLogger("WeeklyRetrainService")

DEFAULT_TRAINING_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
    "XRP/USDT", "DOGE/USDT", "ADA/USDT", "AVAX/USDT",
    "LINK/USDT", "ATOM/USDT", "NEAR/USDT", "SUI/USDT"
]

class WeeklyRetrainService:
    def __init__(
        self,
        pairs: Optional[List[str]] = None,
        timeframe: str = "5m",
        history_days: int = 45,
        min_auc_threshold: float = 0.60
    ):
        self.pairs = pairs or DEFAULT_TRAINING_PAIRS
        self.timeframe = timeframe
        self.history_days = history_days
        self.min_auc_threshold = min_auc_threshold
        
        self.history_dir = PROJECT_ROOT / "data_storage" / "history"
        self.models_dir = PROJECT_ROOT / "data_storage" / "models"
        self.backups_dir = self.models_dir / "backups"
        self.target_model_path = PROJECT_ROOT / settings.MODEL_PATH
        self.history_log_path = PROJECT_ROOT / "data_storage" / "retrain_history.json"
        
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        self.notifier = TelegramNotifier() if getattr(settings, 'ENABLE_TELEGRAM', False) else None

    def download_pair_ohlcv(self, exchange: ccxt.Exchange, symbol: str) -> Optional[pd.DataFrame]:
        """
        Завантажує та інкрементно оновлює історичні свічки з Binance.
        """
        clean_symbol = symbol.replace("/", "_")
        csv_path = self.history_dir / f"{clean_symbol}_{self.timeframe}.csv"
        
        since = exchange.parse8601((datetime.now(timezone.utc) - timedelta(days=self.history_days)).isoformat())
        existing_df = None
        
        if csv_path.exists():
            try:
                existing_df = pd.read_csv(csv_path)
                if not existing_df.empty and "timestamp" in existing_df.columns:
                    last_ts = int(existing_df["timestamp"].max())
                    # Починаємо з останньої збереженої свічки (інкрементне довантаження)
                    since = max(since, last_ts + 1)
            except Exception as e:
                logger.warning(f"⚠️ Помилка читання наявного {csv_path.name}: {e}. Перезавантажую з нуля.")

        logger.info(f"📥 Завантаження свічок для {symbol} (since={datetime.fromtimestamp(since/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')})...")
        new_candles = []
        retries = 0

        while since < exchange.milliseconds() and retries < 4:
            try:
                candles = exchange.fetch_ohlcv(symbol, timeframe=self.timeframe, since=since, limit=1000)
                if not candles:
                    break
                new_candles.extend(candles)
                since = candles[-1][0] + 1
                time.sleep(0.15)  # rate limit pause
            except Exception as e:
                retries += 1
                logger.warning(f"⚠️ Помилка запиту {symbol}: {e}. Спроба {retries}/4...")
                time.sleep(2 * retries)

        if not new_candles and existing_df is None:
            logger.warning(f"❌ Немає даних для {symbol}")
            return None

        new_df = pd.DataFrame(new_candles, columns=["timestamp", "open", "high", "low", "close", "volume"]) if new_candles else pd.DataFrame()
        
        if existing_df is not None and not new_df.empty:
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            combined_df.drop_duplicates(subset=["timestamp"], keep="last", inplace=True)
        elif not new_df.empty:
            combined_df = new_df
        else:
            combined_df = existing_df

        combined_df.sort_values("timestamp", inplace=True)
        combined_df.reset_index(drop=True, inplace=True)
        
        # Обрізаємо занадто старі свічки, залишаючи вікно history_days
        min_allowed_ts = exchange.parse8601((datetime.utcnow() - timedelta(days=self.history_days + 5)).isoformat())
        combined_df = combined_df[combined_df["timestamp"] >= min_allowed_ts].copy()
        
        combined_df.to_csv(csv_path, index=False)
        logger.info(f"✅ {symbol}: збережено {len(combined_df)} свічок у {csv_path.name}")
        return combined_df

    def fetch_all_fresh_data(self) -> int:
        """Завантажує свіжі дані для всього пулу торгових пар."""
        logger.info(f"🌍 Ініціалізація підключення до Binance (CCXT)...")
        exchange = ccxt.binance({"enableRateLimit": True, "timeout": 10000})
        total_candles = 0

        for symbol in self.pairs:
            try:
                df = self.download_pair_ohlcv(exchange, symbol)
                if df is not None:
                    total_candles += len(df)
            except Exception as e:
                logger.error(f"❌ Не вдалося оновити свічки для {symbol}: {e}")

        logger.info(f"🏁 Завантаження завершено. Усього в пулі: {total_candles} свічок.")
        return total_candles

    def prepare_dataset(self) -> pd.DataFrame:
        """Розраховує квант-фічі та Triple-Barrier розмітку для всіх пар."""
        all_labeled = []
        feature_cols = get_feature_columns()

        for symbol in self.pairs:
            clean_symbol = symbol.replace("/", "_")
            csv_path = self.history_dir / f"{clean_symbol}_{self.timeframe}.csv"
            if not csv_path.exists():
                continue

            try:
                df = pd.read_csv(csv_path)
                if len(df) < 200:
                    continue

                # 1. Генерація фіч
                df_feat = calculate_features(df)
                if df_feat.empty or not set(feature_cols).issubset(df_feat.columns):
                    continue

                # 2. Розмітка потрійним бар'єром (TP 1.8 ATR, SL 1.2 ATR, горизонт 12 свічок)
                df_labeled = create_triple_barrier_labels(
                    df_feat, tp_mult=1.8, sl_mult=1.2, horizon=12, min_fee_buffer=0.0025
                )

                if not df_labeled.empty and "Target" in df_labeled.columns:
                    all_labeled.append(df_labeled)
                    logger.debug(f"📊 {symbol}: додано {len(df_labeled)} валідних прикладів")

            except Exception as e:
                logger.warning(f"⚠️ Помилка обробки {symbol}: {e}")

        if not all_labeled:
            raise RuntimeError("Не вдалося сформувати тренувальний датасет з жодного файлу!")

        combined = pd.concat(all_labeled, ignore_index=True)
        # Сортування за часом для коректного TimeSeriesSplit
        if "timestamp" in combined.columns:
            combined.sort_values("timestamp", inplace=True)
            combined.reset_index(drop=True, inplace=True)

        logger.info(f"🎯 Сформовано загальний датасет: {len(combined)} свічок.")
        return combined

    def train_and_validate(self, df: pd.DataFrame) -> Tuple[object, Dict[str, float]]:
        """
        Навчає Random Forest, калібрує через Sigmoid + TimeSeriesSplit,
        та перевіряє Out-Of-Sample метрики.
        """
        features = get_feature_columns()
        X = df[features].copy()
        y = df["Target"].copy()

        X.replace([np.inf, -np.inf], np.nan, inplace=True)
        X.fillna(0.0, inplace=True)

        # 80% навчання, 20% строгий Out-Of-Sample тест
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        class_dist = y_train.value_counts().to_dict()
        logger.info(f"⚙️ Тренувальна вибірка: {len(X_train)} | Тестова: {len(X_test)} | Класи: {class_dist}")

        base_rf = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=30,
            min_samples_leaf=15,
            class_weight="balanced",
            random_state=42,
            n_jobs=1
        )

        unique_classes = np.unique(y_train)
        if len(unique_classes) < 2:
            raise ValueError(f"Тренувальна вибірка містить лише один клас ({unique_classes}). Необхідно мінімум 2 класи.")

        logger.info("🧠 Навчання CalibratedClassifierCV (RandomForest)...")
        try:
            tscv = TimeSeriesSplit(n_splits=3)
            calibrated_model = CalibratedClassifierCV(
                estimator=base_rf,
                method="sigmoid",
                cv=tscv
            )
            calibrated_model.fit(X_train, y_train)
            final_model = calibrated_model
        except Exception as cv_err:
            logger.warning(f"⚠️ TimeSeriesSplit calibration fallback ({cv_err}). Використовую базовий RandomForest...")
            base_rf.fit(X_train, y_train)
            final_model = base_rf

        y_pred = final_model.predict(X_test)
        y_proba = final_model.predict_proba(X_test)[:, 1]

        try:
            auc = float(roc_auc_score(y_test, y_proba))
        except Exception:
            logger.warning("⚠️ Неможливо розрахувати ROC-AUC (у тестовій вибірці присутній лише один клас). Встановлено 0.50.")
            auc = 0.50

        accuracy = float((y_pred == y_test).mean())

        logger.info(f"⭐ Результати валідації: ROC-AUC = {auc:.4f} | Accuracy = {accuracy:.4f}")
        logger.info("\n" + classification_report(y_test, y_pred, zero_division=0))

        metrics = {
            "roc_auc": round(auc, 4),
            "accuracy": round(accuracy, 4),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "positive_rate": round(float(y.mean()), 4)
        }
        return final_model, metrics

    def deploy_model_safely(self, model: object, metrics: Dict[str, float]) -> bool:
        """
        Безпечне розгортання моделі (Quality Gate + Backup + Atomic Swap).
        """
        auc = metrics.get("roc_auc", 0.0)
        
        # 1. Quality Gate: якщо модель показує слабкий результат, не замінюємо робочу модель!
        if auc < self.min_auc_threshold:
            msg = f"❌ [Retrain Gate] Нова модель відхилена! ROC-AUC ({auc:.4f}) нижче мінімального порогу ({self.min_auc_threshold}). Стара модель залишається в строю."
            logger.error(msg)
            if self.notifier:
                self.notifier._sync_post(msg)
            return False

        # 2. Робимо бекап поточної моделі
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if self.target_model_path.exists():
            backup_file = self.backups_dir / f"global_rf_v4_backup_{timestamp_str}.pkl"
            shutil.copy2(self.target_model_path, backup_file)
            logger.info(f"💾 Створено бекап поточної моделі: {backup_file.name}")

        # 3. Атомарний запис нової моделі (через .tmp файл)
        temp_file = self.target_model_path.with_suffix(".tmp")
        joblib.dump(model, temp_file)
        
        if self.target_model_path.exists():
            os.replace(temp_file, self.target_model_path)
        else:
            temp_file.rename(self.target_model_path)

        logger.info(f"🚀 [Deploy] Нова модель успішно активована: {self.target_model_path.name}")

        # 4. Зберігаємо історію перенавчань
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "DEPLOYED",
            "metrics": metrics,
            "pairs_count": len(self.pairs),
            "model_path": str(self.target_model_path)
        }
        self._record_history(log_entry)

        # 5. Telegram сповіщення
        success_msg = (
            f"🔄 <b>[AI Retrain] Щотижневе перенавчання ШІ завершено!</b>\n"
            f"════════════════════════════════\n"
            f"• Модель: <b>Random Forest Calibrated v4</b>\n"
            f"• Валідація ROC-AUC: <b>{auc:.4f}</b> (Поріг &ge; {self.min_auc_threshold})\n"
            f"• Точність (Accuracy): <b>{metrics['accuracy']*100:.1f}%</b>\n"
            f"• Розмір датасету: <b>{metrics['train_samples'] + metrics['test_samples']}</b> свічок\n"
            f"• Статус: <b>Нові ваги розгорнуто наживо ✅</b>\n"
            f"════════════════════════════════"
        )
        if self.notifier:
            self.notifier._sync_post(success_msg)

        return True

    def _record_history(self, entry: dict) -> None:
        try:
            history = []
            if self.history_log_path.exists():
                with open(self.history_log_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            history.append(entry)
            with open(self.history_log_path, "w", encoding="utf-8") as f:
                json.dump(history[-30:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"⚠️ Не вдалося зберегти запис у retrain_history.json: {e}")

    def execute_full_cycle(self) -> bool:
        """
        Повний цикл щотижневого обслуговування ШІ:
        Завантаження свічок -> Розрахунок фіч -> Навчання -> Валідація -> Деплой.
        """
        start_time = time.time()
        logger.info("=" * 60)
        logger.info(f"🚀 СТАРТ ЩОТИЖНЕВОГО ПЕРЕНАВЧАННЯ ШІ ({datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')})")
        logger.info("=" * 60)

        try:
            # 1. Завантаження свічок
            self.fetch_all_fresh_data()

            # 2. Формування датасету
            df = self.prepare_dataset()

            # 3. Навчання та оцінка якості
            model, metrics = self.train_and_validate(df)

            # 4. Атомарне розгортання
            success = self.deploy_model_safely(model, metrics)

            elapsed = time.time() - start_time
            logger.info(f"⏱ Цикл перенавчання виконано за {elapsed:.1f} сек. Результат: {'УСПІХ' if success else 'ВІДХИЛЕНО'}")
            return success

        except Exception as e:
            logger.critical(f"🛑 Критична помилка у конвеєрі перенавчання: {e}", exc_info=True)
            if self.notifier:
                self.notifier._sync_post(f"❌ <b>Помилка щотижневого перенавчання ШІ:</b> {e}")
            return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    service = WeeklyRetrainService(history_days=30)
    service.execute_full_cycle()
