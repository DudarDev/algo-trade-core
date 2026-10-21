"""
Enterprise Automated Feedback Loop & Retraining Service (Continuous Learning Engine).
Аналізує закриті угоди з реального ринку, діагностує патерни помилок,
формує зважений датасет бойового досвіду (X_real, y_real) та здійснює
адаптивне до-навчання моделі Random Forest з Quality Gate перевіркою.
"""

import os
import sys
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ConfigDict
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score, accuracy_score, brier_score_loss

# Корінь проєкту
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.shared.config import settings
from src.shared.db.session import SessionLocal, init_db
from src.shared.db.models import Trade
from src.infrastructure.ai.feature_engineer import get_feature_columns, calculate_features
from src.engine.infrastructure.telegram_notifier import TelegramNotifier

logger = logging.getLogger("FeedbackLoop")

# --- Pydantic Моделі Валідації ---

class PatternBreakdown(BaseModel):
    losses: int = Field(default=0, ge=0)
    wins: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    loss_rate_pct: float = Field(default=0.0, ge=0.0, le=100.0)

    model_config = ConfigDict(strict=True)

class ErrorPatternReport(BaseModel):
    total_trades_analyzed: int = Field(default=0, ge=0)
    total_losses: int = Field(default=0, ge=0)
    total_wins: int = Field(default=0, ge=0)
    overall_win_rate_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    regime_breakdown: Dict[str, PatternBreakdown] = Field(default_factory=dict)
    adx_breakdown: Dict[str, PatternBreakdown] = Field(default_factory=dict)
    rsi_breakdown: Dict[str, PatternBreakdown] = Field(default_factory=dict)
    confidence_breakdown: Dict[str, PatternBreakdown] = Field(default_factory=dict)
    key_findings: List[str] = Field(default_factory=list)
    actionable_recommendations: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = ConfigDict(strict=True)

class FeedbackRetrainResult(BaseModel):
    success: bool
    deployed: bool
    trained_samples: int = Field(default=0, ge=0)
    real_trades_used: int = Field(default=0, ge=0)
    baseline_candles_used: int = Field(default=0, ge=0)
    metrics: Dict[str, float] = Field(default_factory=dict)
    message: str
    backup_path: Optional[str] = None
    updated_model_path: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = ConfigDict(strict=True)


class FeedbackLoopService:
    """
    Сервіс замкненого циклу самонавчання (Feedback Loop Engine).
    """

    def __init__(
        self,
        db_session_factory=SessionLocal,
        model_path: Optional[Path] = None,
        data_dir: Optional[Path] = None,
        min_auc_threshold: float = 0.58
    ):
        self.session_factory = db_session_factory
        self.data_dir = data_dir or (PROJECT_ROOT / "data_storage")
        self.models_dir = self.data_dir / "models"
        self.backups_dir = self.models_dir / "backups"
        self.history_dir = self.data_dir / "history"
        self.history_log_path = self.data_dir / "feedback_retrain_history.json"
        
        target_model = model_path or (PROJECT_ROOT / getattr(settings, "MODEL_PATH", "data_storage/models/global_rf_v4.pkl"))
        self.target_model_path = target_model
        self.min_auc_threshold = float(min_auc_threshold)

        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        self.notifier = TelegramNotifier() if getattr(settings, 'ENABLE_TELEGRAM', False) else None

    def analyze_error_patterns(self, lookback_trades: int = 50) -> ErrorPatternReport:
        """
        Аналізує закриті угоди з бази даних та виявляє статистичні патерни збитків.
        """
        with self.session_factory() as session:
            trades = (
                session.query(Trade)
                .filter(Trade.side == "SELL")
                .order_by(Trade.timestamp.desc())
                .limit(lookback_trades)
                .all()
            )

        if not trades:
            logger.info("ℹ️ [Feedback Loop] Немає закритих угод для аналізу патернів.")
            return ErrorPatternReport(
                total_trades_analyzed=0,
                key_findings=["Історія закритих угод порожня."],
                actionable_recommendations=["Необхідно накопичити бойові угоди для статистичного аналізу."]
            )

        total_trades = len(trades)
        losses_count = 0
        wins_count = 0

        regimes: Dict[str, Dict[str, int]] = {}
        adx_bins: Dict[str, Dict[str, int]] = {
            "ADX < 25 (Флет/Слабкий)": {"losses": 0, "wins": 0, "total": 0},
            "25 <= ADX < 30 (Помірний)": {"losses": 0, "wins": 0, "total": 0},
            "ADX >= 30 (Сильний тренд)": {"losses": 0, "wins": 0, "total": 0}
        }
        rsi_bins: Dict[str, Dict[str, int]] = {
            "RSI < 40 (Перепроданість)": {"losses": 0, "wins": 0, "total": 0},
            "40 <= RSI <= 60 (Нейтрально)": {"losses": 0, "wins": 0, "total": 0},
            "RSI > 60 (Перекупленість)": {"losses": 0, "wins": 0, "total": 0}
        }
        conf_bins: Dict[str, Dict[str, int]] = {
            "Conf < 0.35": {"losses": 0, "wins": 0, "total": 0},
            "0.35 <= Conf < 0.50": {"losses": 0, "wins": 0, "total": 0},
            "Conf >= 0.50": {"losses": 0, "wins": 0, "total": 0}
        }

        for t in trades:
            pnl = float(getattr(t, "pnl", 0.0))
            is_win = (getattr(t, "target_label", 1 if pnl > 0 else 0) == 1 or pnl > 0)
            if is_win:
                wins_count += 1
            else:
                losses_count += 1

            # 1. Режим ринку
            r_name = str(getattr(t, "regime", "CHOPPY_FLAT"))
            if r_name not in regimes:
                regimes[r_name] = {"losses": 0, "wins": 0, "total": 0}
            regimes[r_name]["total"] += 1
            if is_win:
                regimes[r_name]["wins"] += 1
            else:
                regimes[r_name]["losses"] += 1

            # 2. Індикатори зі зрізу фіч
            feat_dict = {}
            raw_feat = getattr(t, "features_json", "{}")
            if raw_feat:
                try:
                    feat_dict = json.loads(raw_feat)
                except Exception:
                    feat_dict = {}

            # ADX
            raw_adx = float(feat_dict.get("ADX", 0.25))
            adx_val = raw_adx * 100.0 if raw_adx <= 1.0 else raw_adx
            if adx_val < 25.0:
                k_adx = "ADX < 25 (Флет/Слабкий)"
            elif adx_val < 30.0:
                k_adx = "25 <= ADX < 30 (Помірний)"
            else:
                k_adx = "ADX >= 30 (Сильний тренд)"
            adx_bins[k_adx]["total"] += 1
            if is_win:
                adx_bins[k_adx]["wins"] += 1
            else:
                adx_bins[k_adx]["losses"] += 1

            # RSI
            raw_rsi = float(feat_dict.get("RSI", 0.50))
            rsi_val = raw_rsi * 100.0 if raw_rsi <= 1.0 else raw_rsi
            if rsi_val < 40.0:
                k_rsi = "RSI < 40 (Перепроданість)"
            elif rsi_val <= 60.0:
                k_rsi = "40 <= RSI <= 60 (Нейтрально)"
            else:
                k_rsi = "RSI > 60 (Перекупленість)"
            rsi_bins[k_rsi]["total"] += 1
            if is_win:
                rsi_bins[k_rsi]["wins"] += 1
            else:
                rsi_bins[k_rsi]["losses"] += 1

            # Confidence
            conf = float(getattr(t, "ai_confidence", 0.0))
            if conf < 0.35:
                k_conf = "Conf < 0.35"
            elif conf < 0.50:
                k_conf = "0.35 <= Conf < 0.50"
            else:
                k_conf = "Conf >= 0.50"
            conf_bins[k_conf]["total"] += 1
            if is_win:
                conf_bins[k_conf]["wins"] += 1
            else:
                conf_bins[k_conf]["losses"] += 1

        # Формуємо Pydantic breakdown
        def to_breakdown_dict(d: dict) -> Dict[str, PatternBreakdown]:
            res = {}
            for k, v in d.items():
                tot = v["total"]
                loss_rate = round((v["losses"] / tot * 100.0), 1) if tot > 0 else 0.0
                res[k] = PatternBreakdown(
                    losses=v["losses"],
                    wins=v["wins"],
                    total=tot,
                    loss_rate_pct=loss_rate
                )
            return res

        regime_breakdown = to_breakdown_dict(regimes)
        adx_breakdown = to_breakdown_dict(adx_bins)
        rsi_breakdown = to_breakdown_dict(rsi_bins)
        conf_breakdown = to_breakdown_dict(conf_bins)

        # Автоматичний синтез ключових висновків
        key_findings = []
        actionable_recommendations = []

        overall_wr = round((wins_count / total_trades * 100.0), 1) if total_trades > 0 else 0.0

        # Пошук слабких зон
        for r_name, r_data in regime_breakdown.items():
            if r_data.total >= 3 and r_data.loss_rate_pct >= 60.0:
                key_findings.append(
                    f"⚠️ Висока частка збитків ({r_data.loss_rate_pct}%) у ринковому режимі '{r_name}' ({r_data.losses}/{r_data.total})."
                )
                actionable_recommendations.append(
                    f"Посилити фільтрацію або підвищити поріг Confidence для режиму {r_name}."
                )

        low_adx_item = adx_breakdown.get("ADX < 25 (Флет/Слабкий)")
        if low_adx_item and low_adx_item.total >= 3 and low_adx_item.loss_rate_pct >= 55.0:
            key_findings.append(
                f"⚠️ Слабкий ADX (<25) генерує {low_adx_item.loss_rate_pct}% хибних входів ({low_adx_item.losses}/{low_adx_item.total})."
            )
            actionable_recommendations.append(
                "Підвищити min_adx_trend з 25.0 до 28.0–30.0, щоб уникати затяжних консолідацій."
            )

        if not key_findings:
            key_findings.append("Розподіл збитків рівномірний, аномальних концентрацій помилок не виявлено.")
            actionable_recommendations.append("Продовжувати планове щотижневе оновлення вагів моделі.")

        report = ErrorPatternReport(
            total_trades_analyzed=total_trades,
            total_losses=losses_count,
            total_wins=wins_count,
            overall_win_rate_pct=overall_wr,
            regime_breakdown=regime_breakdown,
            adx_breakdown=adx_breakdown,
            rsi_breakdown=rsi_breakdown,
            confidence_breakdown=conf_breakdown,
            key_findings=key_findings,
            actionable_recommendations=actionable_recommendations
        )

        logger.info(
            f"🔍 [Error Pattern Analysis] Проаналізовано {total_trades} угод | "
            f"WinRate: {overall_wr}% | Знайдено патернів: {len(key_findings)}"
        )
        return report

    def extract_experience_dataset(self, min_trades: int = 5) -> Optional[Tuple[pd.DataFrame, pd.Series, np.ndarray]]:
        """
        Формує навчальний датасет бойового досвіду (X_real, y_real, sample_weights)
        із закритих угод, збережених у Feature Store.
        """
        with self.session_factory() as session:
            trades = (
                session.query(Trade)
                .filter(Trade.side == "SELL")
                .order_by(Trade.timestamp.asc())
                .all()
            )

        # Фільтруємо угоди, де присутній зріз фіч
        valid_trades = []
        for t in trades:
            raw_feat = getattr(t, "features_json", None)
            if raw_feat and raw_feat.strip() not in ("", "{}"):
                valid_trades.append(t)

        if len(valid_trades) < min_trades:
            logger.info(
                f"ℹ️ [Experience Dataset] Недостатньо бойових угод зі зрізом фіч: "
                f"{len(valid_trades)} < {min_trades}."
            )
            return None

        feature_cols = get_feature_columns()
        rows = []
        labels = []
        weights = []

        total_v = len(valid_trades)
        for idx, t in enumerate(valid_trades):
            try:
                feat_dict = json.loads(t.features_json)
            except Exception:
                continue

            row_data = {}
            for col in feature_cols:
                row_data[col] = float(feat_dict.get(col, 0.0))
            rows.append(row_data)

            pnl = float(getattr(t, "pnl", 0.0))
            label = 1 if (getattr(t, "target_label", 1 if pnl > 0 else 0) == 1 or pnl > 0) else 0
            labels.append(label)

            # Розрахунок ваги прикладу (Sample Weighting):
            # 1. Часовий експоненціальний розпад: новіші угоди мають вищу вагу
            recency_weight = float(np.exp(-0.015 * (total_v - 1 - idx)))

            # 2. Асиметричний штраф за збитки:
            # Збитки (хибні спрацьовування) отримують вагу 1.6x, щоб модель вчилася їх блокувати
            loss_multiplier = 1.6 if label == 0 else 1.0

            # 3. Базовий множник бойового досвіду (порівняно з синтетикою/історією)
            experience_boost = 3.0

            final_w = recency_weight * loss_multiplier * experience_boost
            weights.append(final_w)

        if not rows:
            return None

        df_x = pd.DataFrame(rows, columns=feature_cols).fillna(0.0)
        s_y = pd.Series(labels, dtype=int)
        arr_w = np.array(weights, dtype=float)

        logger.info(
            f"📦 [Experience Dataset] Успішно сформовано: {len(df_x)} реальних прикладів "
            f"(Win: {sum(s_y == 1)}, Loss: {sum(s_y == 0)})"
        )
        return df_x, s_y, arr_w

    def _load_baseline_candles(self, max_candles: int = 1500) -> Optional[Tuple[pd.DataFrame, pd.Series, np.ndarray]]:
        """
        Завантажує фонові історичні свічки з data_storage/history для збереження
        загального контексту ринку та запобігання Catastrophic Forgetting.
        """
        csv_files = list(self.history_dir.glob("*.csv"))
        if not csv_files:
            return None

        dfs = []
        for csv_path in csv_files[:4]:
            try:
                df = pd.read_csv(csv_path)
                if len(df) >= 70:
                    df_feat = calculate_features(df)
                    if not df_feat.empty:
                        # Проста потрійна бар'єрна розмітка для бейслайну
                        ret_fwd = df_feat['close'].shift(-6) / df_feat['close'] - 1.0
                        df_feat['Target'] = (ret_fwd > 0.0035).astype(int)
                        dfs.append(df_feat.dropna().tail(max_candles // max(1, len(csv_files))))
            except Exception as e:
                logger.debug(f"Помилка завантаження бейслайну з {csv_path.name}: {e}")

        if not dfs:
            return None

        combined = pd.concat(dfs, ignore_index=True)
        feature_cols = get_feature_columns()
        valid_cols = [c for c in feature_cols if c in combined.columns]

        X_base = combined[valid_cols].fillna(0.0)
        # Доповнюємо відсутні колонки нулями
        for c in feature_cols:
            if c not in X_base.columns:
                X_base[c] = 0.0
        X_base = X_base[feature_cols]

        y_base = combined['Target'].astype(int)
        w_base = np.ones(len(combined), dtype=float)  # Базова вага = 1.0

        return X_base, y_base, w_base

    def retrain_with_feedback(
        self,
        min_real_trades: int = 5,
        force_deploy: bool = False
    ) -> FeedbackRetrainResult:
        """
        Головний конвеєр до-навчання:
        1. Витягує бойовий датасет досвіду (X_real, y_real, w_real).
        2. Об'єднує з історичним бейслайном (X_base, y_base, w_base).
        3. Тренує калібровану модель з акцентом на усунення помилок.
        4. Застосовує Quality Gate (ROC-AUC >= min_auc_threshold).
        5. Здійснює безпечний атомарний Swap моделі.
        """
        logger.info("🧠 [Feedback Loop] Запуск циклу самонавчання...")

        exp_data = self.extract_experience_dataset(min_trades=min_real_trades)
        if exp_data is None:
            msg = f"Пропуск: Недостатньо бойового досвіду для безпечного до-навчання (потрібно мінімум {min_real_trades} угод зі зрізом фіч)."
            logger.info(f"ℹ️ {msg}")
            return FeedbackRetrainResult(
                success=False,
                deployed=False,
                trained_samples=0,
                real_trades_used=0,
                baseline_candles_used=0,
                message=msg
            )

        X_real, y_real, w_real = exp_data
        real_count = len(X_real)

        # Завантажуємо бейслайн
        baseline_data = self._load_baseline_candles()
        if baseline_data is not None:
            X_base, y_base, w_base = baseline_data
            X_train = pd.concat([X_base, X_real], ignore_index=True)
            y_train = pd.concat([y_base, y_real], ignore_index=True)
            w_train = np.concatenate([w_base, w_real])
            base_count = len(X_base)
        else:
            X_train = X_real
            y_train = y_real
            w_train = w_real
            base_count = 0

        # Перевіряємо наявність обох класів
        unique_classes = np.unique(y_train)
        if len(unique_classes) < 2:
            msg = f"Відхилено: у збірному датасеті присутній лише один клас {unique_classes}."
            logger.warning(f"⚠️ {msg}")
            return FeedbackRetrainResult(
                success=False,
                deployed=False,
                trained_samples=len(X_train),
                real_trades_used=real_count,
                baseline_candles_used=base_count,
                message=msg
            )

        logger.info(
            f"🔄 Навчання моделі на {len(X_train)} зразках "
            f"({real_count} реальних угод + {base_count} фонових свічок)..."
        )

        # Розбиття на train/test за часовим рядом (останні 20% на out-of-sample тест)
        split_idx = int(len(X_train) * 0.80)
        X_tr, X_val = X_train.iloc[:split_idx], X_train.iloc[split_idx:]
        y_tr, y_val = y_train.iloc[:split_idx], y_train.iloc[split_idx:]
        w_tr, w_val = w_train[:split_idx], w_train[split_idx:]

        # Базовий Random Forest із підвищеною стійкістю до шуму
        base_rf = RandomForestClassifier(
            n_estimators=100,
            max_depth=7,
            min_samples_split=8,
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=42,
            n_jobs=1
        )

        try:
            # Навчаємо базову модель з вагами прикладів
            base_rf.fit(X_tr, y_tr, sample_weight=w_tr)

            # Калібрація ймовірностей (Sigmoid Platt scaling)
            calibrated_model = CalibratedClassifierCV(
                estimator=base_rf,
                method="sigmoid",
                cv="prefit"
            )
            # Якщо у валідаційній вибірці є обидва класи – калібруємо на ній
            if len(np.unique(y_val)) >= 2:
                calibrated_model.fit(X_val, y_val)
                final_model = calibrated_model
            else:
                final_model = base_rf

        except Exception as fit_err:
            logger.warning(f"⚠️ Помилка калібрації: {fit_err}. Використовую чистий Random Forest.")
            base_rf.fit(X_train, y_train, sample_weight=w_train)
            final_model = base_rf

        # Валідація на тестовій вибірці
        y_val_proba = final_model.predict_proba(X_val)[:, 1]
        y_val_pred = (y_val_proba >= 0.50).astype(int)

        try:
            auc = float(roc_auc_score(y_val, y_val_proba))
        except Exception:
            auc = 0.50

        acc = float(accuracy_score(y_val, y_val_pred))
        brier = float(brier_score_loss(y_val, y_val_proba))

        metrics = {
            "roc_auc": round(auc, 4),
            "accuracy": round(acc, 4),
            "brier_score": round(brier, 4),
            "total_samples": len(X_train),
            "real_trades": real_count,
            "baseline_candles": base_count
        }

        logger.info(f"📊 Метрики валідації: ROC-AUC = {auc:.4f} | Accuracy = {acc:.4f} | Brier = {brier:.4f}")

        # Quality Gate
        if auc < self.min_auc_threshold and not force_deploy:
            msg = (
                f"❌ Quality Gate не пройдено: ROC-AUC ({auc:.4f}) нижче допустимого порогу "
                f"({self.min_auc_threshold}). Робоча модель не змінюється."
            )
            logger.warning(f"🛡️ {msg}")
            return FeedbackRetrainResult(
                success=True,
                deployed=False,
                trained_samples=len(X_train),
                real_trades_used=real_count,
                baseline_candles_used=base_count,
                metrics=metrics,
                message=msg
            )

        # Розгортання (Atomic Deployment)
        backup_str = None
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # 1. Бекап старої моделі, якщо вона існує
        if self.target_model_path.exists():
            backup_file = self.backups_dir / f"{self.target_model_path.stem}_backup_{ts_str}.pkl"
            shutil.copy2(self.target_model_path, backup_file)
            backup_str = str(backup_file)
            logger.info(f"💾 Створено бекап існуючої моделі: {backup_file.name}")

        # 2. Збереження у тимчасовий файл і атомарна заміна
        temp_file = self.target_model_path.with_suffix(".tmp")
        joblib.dump(final_model, temp_file)
        shutil.move(temp_file, self.target_model_path)

        success_msg = (
            f"🎉 [Feedback Loop] Модель успішно перенавчено на реальному досвіді бота та розгорнуто! "
            f"ROC-AUC = {auc:.4f}, Accuracy = {acc:.4f}, Використано угод: {real_count}."
        )
        logger.info(success_msg)

        # 3. Аудит-лог
        self._append_audit_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "real_trades_used": real_count,
            "baseline_candles_used": base_count,
            "metrics": metrics,
            "backup_path": backup_str,
            "target_model_path": str(self.target_model_path)
        })

        if self.notifier:
            self.notifier._sync_post(f"🤖 <b>Continuous Learning Update</b>\n{success_msg}")

        return FeedbackRetrainResult(
            success=True,
            deployed=True,
            trained_samples=len(X_train),
            real_trades_used=real_count,
            baseline_candles_used=base_count,
            metrics=metrics,
            message=success_msg,
            backup_path=backup_str,
            updated_model_path=str(self.target_model_path)
        )

    def _append_audit_log(self, record: dict) -> None:
        logs = []
        if self.history_log_path.exists():
            try:
                with open(self.history_log_path, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []
        logs.append(record)
        try:
            with open(self.history_log_path, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Не вдалося оновити лог самонавчання: {e}")
