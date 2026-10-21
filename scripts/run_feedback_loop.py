"""
CLI скрипт для запуску конвеєра самонавчання та аналізу патернів помилок.
Використання:
    python scripts/run_feedback_loop.py --analyze-only
    python scripts/run_feedback_loop.py --min-trades 5
"""

import sys
import argparse
from pathlib import Path

# Фікс для виводу символів у консоль Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.infrastructure.ai.feedback_loop import FeedbackLoopService

def main():
    parser = argparse.ArgumentParser(description="Continuous Learning & Feedback Loop Runner")
    parser.add_argument("--analyze-only", action="store_true", help="Лише провести діагностику патернів без запуску перенавчання")
    parser.add_argument("--min-trades", type=int, default=5, help="Мінімальна кількість угод для запуску перенавчання (за замовчуванням: 5)")
    parser.add_argument("--lookback", type=int, default=50, help="Кількість останніх угод для діагностики помилок (за замовчуванням: 50)")
    parser.add_argument("--force", action="store_true", help="Примусове розгортання без перевірки мінімального порогу AUC")
    args = parser.parse_args()

    service = FeedbackLoopService()

    print("\n" + "="*70)
    print("🧠 QUANTUM FEEDBACK LOOP & CONTINUOUS LEARNING ENGINE")
    print("="*70)

    # 1. Аналіз патернів
    report = service.analyze_error_patterns(lookback_trades=args.lookback)
    print(f"\n📊 Проаналізовано закритих угод: {report.total_trades_analyzed}")
    print(f"📈 Загальний Вінрейт: {report.overall_win_rate_pct}% ({report.total_wins} перемог / {report.total_losses} збитків)")

    print("\n🔍 РОЗПОДІЛ ЗА РЕЖИМАМИ РИНКУ:")
    for reg, data in report.regime_breakdown.items():
        print(f"  • {reg:<15}: Всього={data.total:>2} | Збитки={data.losses:>2} ({data.loss_rate_pct:>5.1f}%) | Перемоги={data.wins:>2}")

    print("\n⚡ РОЗПОДІЛ ЗА СИЛОЮ ТРЕНДУ (ADX):")
    for adx_range, data in report.adx_breakdown.items():
        print(f"  • {adx_range:<26}: Всього={data.total:>2} | Збитки={data.losses:>2} ({data.loss_rate_pct:>5.1f}%)")

    print("\n🎯 ДІАГНОСТИЧНІ ВИСНОВКИ:")
    for finding in report.key_findings:
        print(f"  {finding}")

    print("\n💡 РЕКОМЕНДОВАНІ ДІЇ:")
    for rec in report.actionable_recommendations:
        print(f"  • {rec}")

    if args.analyze_only:
        print("\n" + "="*70)
        print("✅ Аналіз завершено (--analyze-only). Перенавчання не запускалося.")
        print("="*70)
        return

    # 2. До-навчання моделі
    print("\n" + "-"*70)
    print("🚀 ЗАПУСК КОНВЕЄРА САМОНАВЧАННЯ (RETRAINING)...")
    print("-"*70)

    result = service.retrain_with_feedback(
        min_real_trades=args.min_trades,
        force_deploy=args.force
    )

    print(f"\nРезультат: {'УСПІХ' if result.success else 'ВІДХИЛЕНО / ПРОПУСК'}")
    print(f"Розгорнуто в прод: {'ТАК' if result.deployed else 'НІ'}")
    print(f"Повідомлення: {result.message}")
    if result.metrics:
        print(f"Метрики: ROC-AUC={result.metrics.get('roc_auc', 'N/A')} | Accuracy={result.metrics.get('accuracy', 'N/A')} | Brier={result.metrics.get('brier_score', 'N/A')}")
        print(f"Вибірка: Реальних угод={result.real_trades_used} | Фонові свічки={result.baseline_candles_used} | Всього={result.trained_samples}")

    print("="*70 + "\n")

if __name__ == "__main__":
    main()
