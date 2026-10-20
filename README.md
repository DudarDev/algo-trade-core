# 🤖 Algo-Trade-Core (v4.0)
**AI-Powered High-Frequency Crypto Scalping Bot**

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker)
![Machine Learning](https://img.shields.io/badge/AI-Gradient%20Boosting-FF6F00?style=flat-square&logo=scikit-learn)
![Binance](https://img.shields.io/badge/Exchange-Binance-F3BA2F?style=flat-square&logo=binance)

**Algo-Trade-Core** is an advanced, high-frequency algorithmic trading engine designed for highly volatile cryptocurrency markets. It leverages **Machine Learning (Calibrated Random Forest / Gradient Boosting)** to filter out market noise and executes trades using a dynamic, regime-aware Smart Exit strategy.

---

## 🚀 Key Features

* **🧠 AI Brain v4.0:** Utilizes advanced ML models trained on a rich feature set (RSI, MACD_HIST, ATR, EMA distances). The model is continuously calibrated to output *realistic* probabilities.
* **🌐 Multi-Pair Scanner:** Concurrently monitors and evaluates historical & real-time data across top liquid pairs (BTC, ETH, SOL, XRP, etc.) on the Binance network.
* **🛡️ Dynamic Risk Management:**
  * **Regime-Aware Thresholds:** Automatically adjusts AI confidence thresholds based on the current market state (Bull, Bear, or Choppy).
  * **Smart Exit Logic:** Dynamic Risk/Reward ratio targeting (e.g., 2.0 R:R) with strict trailing Stop-Loss protocols to protect capital.
  * **Fee Awakening Protocol:** Strict filters ensure the bot only takes trades that mathematically overcome standard exchange maker/taker fees (0.25%).
* **🛠️ Full Backtesting Engine:** Built-in portfolio backtester (`backtest.py`) that simulates real-world trading, accounting for fees and precise historical data.
* **☁️ Cloud Ready:** Fully Dockerized architecture (with `docker-compose`) for seamless deployment on AWS EC2, Google Cloud, or any VPS.

---

## 🏗️ Architecture Overview

The system is split into two primary "universes":
1. **The Engine (Matrix):** Connects to the exchange, listens to live market data, queries the AI model, evaluates risk via Pydantic schemas, and executes real trades.
2. **The Backtester (Laboratory):** A highly accurate simulation environment to test new ML models and threshold calibrations before deploying them to production.

---

## ⚙️ Installation & Setup

### Option 1: Docker Compose (Recommended for Production / VPS)
This is the safest and most reliable way to run the bot 24/7.

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/DudarDev/algo-trade-core.git](https://github.com/DudarDev/algo-trade-core.git)
   cd algo-trade-core
Build and start the Engine:

Bash
sudo docker compose -f infrastructure/docker-compose.yml up -d --build engine
Check live logs:

Bash
sudo docker logs -f algo_engine
Option 2: Local Python Environment (For Development)
Install dependencies:

Bash
pip install -r requirements.txt
Run the Backtester (Simulation):

Bash
python backtest.py
Run the Live Bot:

Bash
python main.py
🎛️ Configuration (.env)
The bot operates safely out-of-the-box in Paper Trading Mode (Virtual Capital). To enable live trading on Binance, configure your environment variables:

Create a .env file in the root directory:

Фрагмент коду
# Exchange Credentials
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Trading Parameters
TRADING_CONFIDENCE_THRESHOLD=0.25
TRADING_RISK_REWARD_RATIO=2.0
(See src/engine/config/trading_settings.py for full configuration options).

📊 CI/CD Automation
This repository is equipped with GitHub Actions. Pushing to the feature/senior-architecture-refactor (or main) branch automatically triggers a deployment script (infrastructure/deploy.sh) on the designated AWS EC2 instance, ensuring zero-downtime updates.

⚠️ Disclaimer
Educational Purposes Only. This software is provided for educational and research purposes. Algorithmic trading in cryptocurrency markets involves substantial risk of loss. The developers of this software are not responsible for any financial losses incurred from using this bot in live environments. Always test strategies thoroughly in the Backtester before allocating real capital.

Developed with ❤️ by Yaroslav Dudar


### Що змінилося і чому це краще:
1. **Стиль:** Додані бейджики (графічні ярлики Python, Docker, Binance), які одразу показують стек технологій.
2. **Професійна термінологія:** Замість простих слів я використав терміни з Quant-світу (`Regime-Aware Thresholds`, `Fee Awakening Protocol`, `Calibrated Random Forest`), що показує твій рівень як архітектора.
3. **Архітектура:** Коротко описано, що проєкт розділений на Бойовий рушій та Бектестер.
4. **CI/CD:** Додано згадку про те, що ти використовуєш GitHub Actions для автоматичного деплою на AWS (це величезний плюс для резюме).
5. **Англійська:** Відшліфована граматика та структура тексту.

Збережи це, і твій GitHub профіль виглядатиме дуже солідно!