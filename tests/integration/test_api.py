import json
from django.test import Client

def test_bot_status_endpoint():
    client = Client()
    response = client.get('/api/monitor/status')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'bot_status' in data

def test_bot_control_endpoint():
    client = Client()
    response = client.post('/api/monitor/control',
                           data=json.dumps({'command': 'start'}),
                           content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data['bot_status'] == 'active'

    response = client.post('/api/monitor/control',
                           data=json.dumps({'command': 'stop'}),
                           content_type='application/json')
    data = json.loads(response.content)
    assert data['bot_status'] == 'stopped'

    # Відновлюємо активний стан після тесту
    client.post('/api/monitor/control',
                data=json.dumps({'command': 'start'}),
                content_type='application/json')


def test_backtest_endpoint():
    client = Client()
    payload = {
        "symbol": "ETH/USDT",
        "timeframe": "5m",
        "candles": 100,
        "confidence_threshold": 0.20,
        "risk_reward_ratio": 1.5,
        "trade_fraction": 0.04
    }
    response = client.post('/api/monitor/backtest',
                           data=json.dumps(payload),
                           content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert "results" in data
    assert "win_rate" in data["results"]


def test_portfolio_endpoint():
    client = Client()
    response = client.get('/api/monitor/portfolio')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert "portfolio" in data
    assert "bnb_optimizer" in data["portfolio"]


def test_sentiment_endpoint():
    client = Client()
    response = client.get('/api/monitor/sentiment')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert "sentiment" in data
    assert "score" in data["sentiment"]
    assert "risk_mode" in data["sentiment"]


def test_news_endpoint():
    client = Client()
    response = client.get('/api/monitor/news')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert "news" in data
    assert "blackouts" in data
    assert isinstance(data["news"], list)
