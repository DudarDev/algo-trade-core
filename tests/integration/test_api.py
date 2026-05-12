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
