"""Production profile: trusted origin, offline startup and durable private sessions."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from tests.test_controller import NOW


@pytest.fixture
def production(monkeypatch):
    # Do not import a developer's ignored .env into deployment checks.
    monkeypatch.setattr('backend.main.load_dotenv', lambda *args: None)
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('MODEL_MODE', 'live')
    monkeypatch.setenv('OPENAI_API_KEY', 'unused-private-test-key')
    monkeypatch.delenv('SESSION_ENCRYPTION_KEY', raising=False)
    monkeypatch.delenv('ALLOWED_ORIGINS', raising=False)
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://claimflow-test.onrender.com')


def test_render_profile_and_restart(tmp_path, production):
    origin = 'https://claimflow-test.onrender.com'
    with TestClient(create_app(tmp_path, clock=lambda: NOW), base_url=origin) as client:
        assert client.get('/api/health').json()['mode'] == 'scripted'
        for path in ('/api/docs', '/openapi.json', '/.env', '/data/sessions.sqlite3',
                     '/insurance_claims/fixtures/claims.json'):
            assert client.get(path).status_code == 404
        response = client.post('/api/session', headers={'origin': origin})
        assert response.status_code == 200
        assert all(flag in response.headers['set-cookie'].lower() for flag in
                   ('secure', 'httponly', 'samesite=strict'))
        state = response.json()
        client.headers['x-csrf-token'] = state['csrf']
        assert not client.get('/api/settings').json()['local_credentials_allowed']
        assert client.post('/api/session', headers={'origin': 'https://attacker.example'}).status_code == 403
        assert client.post('/api/turn', json={'text': 'hello', 'version': state['version'],
                           'request_id': str(uuid4())}, headers={'x-csrf-token': 'wrong'}).status_code == 403
        state = client.post('/api/turn', json={'text': 'hello', 'version': state['version'],
                            'request_id': str(uuid4())}).json()
        cookies = client.cookies
        client.app.state.store.reserve_tokens(12000, 200000, NOW)
    with TestClient(create_app(tmp_path, clock=lambda: NOW), base_url=origin) as restarted:
        restarted.cookies.update(cookies)
        assert restarted.get('/api/session').json()['version'] == state['version']
        with restarted.app.state.store.db() as db:
            assert db.execute('SELECT tokens FROM budget').fetchone()['tokens'] == 12000


@pytest.mark.parametrize('origin', ['', 'http://claimflow.example', 'https://*.example',
    'https://claimflow.example/path', 'https://user:password@claimflow.example',
    'https://claimflow.example?query=1', 'https://claimflow.example#fragment',
    'https://claimflow.example:invalid', 'https://claim flow.example'])
def test_production_rejects_missing_or_unsafe_origin(tmp_path, production, monkeypatch, origin):
    monkeypatch.setenv('RENDER_EXTERNAL_URL', origin)
    with pytest.raises(ValueError):
        create_app(tmp_path)


def test_explicit_custom_origins_override_render(tmp_path, production, monkeypatch):
    monkeypatch.setenv('ALLOWED_ORIGINS', ' https://demo.example/, https://other.example ')
    with TestClient(create_app(tmp_path), base_url='https://demo.example') as client:
        for origin in ('https://demo.example', 'https://other.example'):
            assert client.post('/api/session', headers={'origin': origin}).status_code == 200
        assert client.post('/api/session', headers={'origin': 'https://claimflow-test.onrender.com'}).status_code == 403
