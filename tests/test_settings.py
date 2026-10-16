from uuid import uuid4
from fastapi.testclient import TestClient
import pytest
from backend.main import create_app
from backend.interpreter import ModelFailure, ScriptedInterpreter
from backend.models import Interpretation
from tests.test_api import send
from tests.test_controller import NOW

SECRET='private-settings-key'

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY','demo-key')
    class MockProvider:
        name='claude-sonnet-5-5'
        async def interpret(self,text,state):
            assert not state.identity  # Connection validation uses a fresh empty context.
            return Interpretation(),{'tokens':20,'latency_ms':1}
    monkeypatch.setattr('backend.settings.make_interpreter',lambda *a:MockProvider())
    with TestClient(create_app(tmp_path,ScriptedInterpreter(),clock=lambda:NOW)) as c:
        s=c.post('/api/session').json();c.headers['x-csrf-token']=s['csrf']
        yield c


def change(client,**kw):
    payload={'request_id':str(uuid4()),'version':client.get('/api/session').json()['version'],
             'provider':'anthropic','model':'claude-sonnet-5-5','credential_source':'byok','api_key':SECRET,**kw}
    return client.post('/api/settings',json=payload)


def test_validated_change_revokes_authorization_consent_and_hides_key(client,tmp_path):
    s=send(client,'My name is Margaret Chen, DOB 1985-03-15, SSN last four 4472. My denied healthcare claim from January.').json()
    s=client.post('/api/action',json={'request_id':str(uuid4()),'version':s['version'],'action':'preview'}).json()
    old=s['summary']['id']
    r=change(client)
    assert r.status_code==200
    data=r.json();s=data['session']
    assert not s['verified'] and s['summary'] is None and not s['messages']
    assert s['model']=='claude-sonnet-5-5' and data['settings']['current']['validated_at']==NOW
    assert SECRET not in r.text and 'api_key' not in r.text
    assert client.post('/api/action',json={'request_id':str(uuid4()),'version':s['version'],'action':'send','summary_id':old}).status_code==403
    assert SECRET.encode() not in (tmp_path/'sessions.sqlite3').read_bytes()
    app=client.app
    state,_=app.state.store.load(client.cookies['claimflow_session'],NOW)
    assert state.model_settings.api_key==SECRET and state.verification_attempts==1 and state.turns==1
    assert SECRET not in client.get('/api/settings').text
    with TestClient(create_app(tmp_path,ScriptedInterpreter(),clock=lambda:NOW)) as resumed:
        resumed.cookies.update(client.cookies)
        assert resumed.get('/api/settings').json()['current']['credential_source']=='byok'
    assert 'scripted'==client.post('/api/session').json()['model']
    assert client.get('/api/settings').json()['current']['provider']=='scripted'


@pytest.mark.parametrize('patch,status',[
    ({'provider':'evil'},422),({'model':'https://attacker.example'},409),
    ({'endpoint':'https://attacker.example'},422),({'credential_source':'demo'},409),
    ({'api_key':None},409),({'api_key':'secret\nheader'},422),({'api_key':'x'*513},422),
    ({'api_key':{'secret':SECRET}},422),({'provider':'scripted','model':'scripted'},409),
])
def test_bad_settings_never_echo_key_or_mutate(client,patch,status):
    before=client.get('/api/session').json()
    r=change(client,**patch)
    assert r.status_code==status and SECRET not in r.text
    assert client.get('/api/session').json()==before


def test_missing_demo_key_csrf_origin_version_and_lease(client):
    assert change(client,provider='gemini',model='gemini-3.8-flash',credential_source='demo',api_key=None).status_code==409
    client.headers['x-csrf-token']='wrong'
    assert change(client).status_code==403
    s=client.get('/api/session').json();client.headers['x-csrf-token']=s['csrf']
    assert change(client,version=99).status_code==409
    assert client.post('/api/settings',json={},headers={'origin':'https://attacker.example'}).status_code==403
    store=client.app.state.store;cookie=client.cookies['claimflow_session']
    _,lease=store.acquire(cookie,'busy',0,'busy',NOW)
    assert change(client).status_code==409
    store.release(cookie,lease)


def test_failed_connection_keeps_workflow_and_reserved_budget(client,monkeypatch):
    class Failure:
        name='claude-sonnet-5-5'
        async def interpret(self,*args): raise ModelFailure('The provider rejected these credentials or model access. Check the key and permissions.')
    monkeypatch.setattr('backend.settings.make_interpreter',lambda *a:Failure())
    before=client.get('/api/session').json()
    r=change(client)
    assert r.status_code==503 and 'credentials' in r.text and SECRET not in r.text
    assert client.get('/api/session').json()==before
    with client.app.state.store.db() as db:
        assert db.execute('SELECT tokens FROM budget').fetchone()['tokens']==12000


def test_switch_dedup_stale_turn_and_offline_no_provider_call(client):
    body={'request_id':str(uuid4()),'version':0,'provider':'scripted','model':'scripted','credential_source':'demo'}
    # Use the real offline adapter rather than the test provider factory.
    from backend.providers import make_interpreter
    import backend.settings
    old=backend.settings.make_interpreter
    backend.settings.make_interpreter=make_interpreter
    try:
        first=client.post('/api/settings',json=body)
        assert first.status_code==200
        assert client.post('/api/settings',json=body).json()==first.json()
        assert client.post('/api/turn',json={'request_id':str(uuid4()),'version':0,'text':'hello'}).status_code==409
        assert client.post('/api/settings',json={**body,'model':'other'}).status_code==409
        assert send(client,'hello').status_code==200
    finally: backend.settings.make_interpreter=old


def test_settings_service_is_independent_of_controller(monkeypatch):
    from backend.settings import Settings,SettingsRequest
    from backend.models import Session
    service=Settings(ScriptedInterpreter())
    request=SettingsRequest(request_id=uuid4(),version=0,provider='anthropic',model='claude-sonnet-5-5',credential_source='byok',api_key=SECRET)
    candidate=service.candidate(request)
    assert candidate.api_key==SECRET and SECRET not in str(candidate)
    assert SECRET not in str(service.public(Session(model_settings=candidate)))
