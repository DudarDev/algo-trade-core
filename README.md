🤖 AI-Powered Crypto Scalping Bot (v4.0)

A high-frequency trading bot designed for volatile crypto markets. It uses Machine Learning (Gradient Boosting) to filter signals and a Smart Exit strategy to secure profits.

🚀 Key Features

Multi-Pair Scanner: Monitors top 10 liquid pairs (BTC, ETH, SOL, etc.) simultaneously on Binance/Binance US.

AI Brain v3.1: Uses GradientBoostingClassifier trained on RSI, MACD, and Bollinger Bands to predict price movements.

Smart Exit Logic:

Take Profit: Auto-sell at +0.7% (configurable).

Stop Loss: Protects capital at -1.5%.

Fee Protection: Ignores signals that don't cover exchange fees.

Cloud Ready: Dockerized for easy deployment on Google Cloud (Free Tier) or AWS.

🛠️ Installation

Option 1: Quick Start (Docker)

This is the recommended way to run the bot 24/7 on a VPS.

Clone the repo:

git clone [https://github.com/YOUR_USERNAME/algo-trade-core.git](https://github.com/YOUR_USERNAME/algo-trade-core.git)
cd algo-trade-core


Build & Run:

docker build -t ai-bot .
docker run -d --restart=always --name my-bot ai-bot


Option 2: Local Python Run

Install dependencies:

pip install -r requirements.txt


Run the bot:

python main.py


⚙️ Configuration

The bot works out-of-the-box in Paper Trading Mode (Virtual Money).
To trade with real money, create a .env file:

API_KEY=your_binance_api_key
API_SECRET=your_binance_secret


📊 Strategy Overview

The bot operates on a 5-minute timeframe.

Data Collection: Fetches OHLCV data for 10 pairs.

Training: If the market is volatile, the AI retrains itself on the latest data.

Signal Generation: The AI predicts a BUY only if confidence is > 70%.

Execution: Enters trade and monitors PnL every second.

⚠️ Disclaimer

This software is for ed