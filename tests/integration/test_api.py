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


def test_system_infra_endpoint():
    client = Client()
    response = client.get('/api/monitor/system_infra')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert "redis" in data
    assert "celery" in data
    assert "ai_ensemble" in data
    assert data["ai_ensemble"]["ensemble_enabled"] is True
    assert "rf" in data["ai_ensemble"]["weights"]
    assert "lightgbm" in data["ai_ensemble"]["weights"]


def test_stream_telemetry_endpoint():
    client = Client()
    response = client.get('/api/monitor/stream')
    assert response.status_code == 200
    assert response['Content-Type'] == 'text/event-stream'
    # Read the first event chunk
    content = next(response.streaming_content).decode('utf-8')
    assert "event: connected" in content


def test_ai_chat_endpoint():
    client = Client()
    payload = {
        "query": "Який поточний статус бота?",
        "lang": "ua"
    }
    response = client.post('/api/monitor/ai/chat',
                           data=json.dumps(payload),
                           content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert "reply" in data
    assert len(data["reply"]) > 10


def test_config_get_and_update():
    client = Client()
    get_res = client.get('/api/monitor/config')
    assert get_res.status_code == 200
    data = json.loads(get_res.content)
    assert "confidence_threshold" in data
    assert "trading_mode" in data

    update_payload = {
        "confidence_threshold": 0.32,
        "risk_reward_ratio": 1.6,
        "max_positions": 4,
        "trade_fraction": 0.05,
        "min_adx_trend": 26.0,
        "trading_mode": "PAPER"
    }
    post_res = client.post('/api/monitor/config',
                           data=json.dumps(update_payload),
                           content_type='application/json')
    assert post_res.status_code == 200
    res_data = json.loads(post_res.content)
    assert res_data["status"] == "success"
    assert res_data["config"]["confidence_threshold"] == 0.32


def test_equity_history_endpoint():
    client = Client()
    response = client.get('/api/monitor/equity_history')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert "current_equity" in data
    assert "equity_curve" in data
    assert "daily_pnl" in data


def test_telegram_test_endpoint_missing_token():
    client = Client()
    response = client.post('/api/monitor/telegram/test',
                           data=json.dumps({"token": "", "chat_id": ""}),
                           content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "error"


def test_ai_error_patterns_endpoint():
    client = Client()
    response = client.get('/api/monitor/ai/error_patterns')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"
    assert "report" in data


def test_ai_trigger_feedback_loop_endpoint():
    client = Client()
    response = client.post('/api/monitor/ai/trigger_feedback_loop',
                           data=json.dumps({'min_real_trades': 100}),
                           content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'status' in data


def test_delta_neutral_funding_and_positions_endpoints():
    client = Client()
    # 1. Тест /arbitrage/funding
    res_funding = client.get('/api/monitor/arbitrage/funding')
    assert res_funding.status_code == 200
    data_f = json.loads(res_funding.content)
    assert 'active_delta_neutral_positions' in data_f
    assert 'total_accrued_funding' in data_f

    # 2. Тест /delta_neutral/positions
    res_pos = client.get('/api/monitor/delta_neutral/positions')
    assert res_pos.status_code == 200
    data_p = json.loads(res_pos.content)
    assert 'positions' in data_p

    # 3. Тест /delta_neutral/open
    res_open = client.post(
        '/api/monitor/delta_neutral/open',
        data=json.dumps({'symbol': 'NEAR/USDT', 'notional': 100.0, 'rate_8h': 0.0003}),
        content_type='application/json'
    )
    assert res_open.status_code == 200
    assert json.loads(res_open.content)['status'] == 'success'

