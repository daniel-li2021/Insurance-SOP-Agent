import asyncio
from uuid import uuid4
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.interpreter import ScriptedInterpreter, ModelFailure
from backend.evaluation import OPENING, scenarios, run_scenario
from backend.store import Conflict, Limited, Store
from backend.models import Session
import pytest
from tests.test_controller import NOW


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path, ScriptedInterpreter(), clock=lambda:NOW)
    with TestClient(app) as client:
        s = client.post('/api/session').json()
        client.headers['x-csrf-token'] = s['csrf']
        yield client


def send(client,text,request_id=None):
    s=client.get('/api/session').json()
    return client.post('/api/turn',json={'text':text,'version':s['version'],'request_id':request_id or str(uuid4())})


@pytest.mark.parametrize('scenario_id', ['standard', 'frustrated', 'ambiguous'])
def test_demo_starters_exercise_the_named_workflow(client, scenario_id):
    demo = client.get('/api/demo-starter').json()
    opening = next(s['opening'] for s in demo['scenarios'] if s['id'] == scenario_id)
    state = send(client, opening).json()
    if scenario_id == 'frustrated':
        assert not state['verified'] and state['case_id'] is None
        assert 'frustrating' in state['messages'][-1]['text']
        state = send(client, demo['opening']).json()
    if scenario_id == 'ambiguous':
        assert state['verified'] and state['phase'] == 'RESOLVE_INTENT'
        assert {c['case_id'] for c in state['choices']} == {'CL-2011', 'CL-2048'}
    else:
        assert state['verified'] and state['case_id'] == 'CL-2048'


def test_full_http_flow_and_duplicate_request(client):
    request_id=str(uuid4())
    s=send(client,"My name is Margaret Chen, DOB 1985-03-15, SSN last four 4472. My denied healthcare claim from January.",request_id).json()
    assert s['verified'] and s['case_id']=='CL-2048'
    retry=client.post('/api/turn',json={'text':"My name is Margaret Chen, DOB 1985-03-15, SSN last four 4472. My denied healthcare claim from January.",'version':0,'request_id':request_id})
    assert retry.status_code==200 and retry.json()['version']==s['version']
    s=client.post('/api/action',json={'action':'preview','version':s['version'],'request_id':str(uuid4())}).json()
    assert s['summary']['status']=='offered'
    body={'action':'send','summary_id':s['summary']['id'],'version':s['version'],'request_id':str(uuid4())}
    first=client.post('/api/action',json=body).json()
    second=client.post('/api/action',json=body).json()
    assert first['summary']['receipt']==second['summary']['receipt']
    assert sum(e['code']=='EMAIL_SIMULATED' for e in second['events'])==1


def test_csrf_origin_and_session_isolation(client,tmp_path):
    assert client.post('/api/turn',json={'text':'hi','version':0,'request_id':str(uuid4())},headers={'x-csrf-token':'wrong'}).status_code==403
    assert client.post('/api/session',headers={'origin':'https://attacker.example'}).status_code==403
    with TestClient(create_app(tmp_path,ScriptedInterpreter(),clock=lambda:NOW)) as other:
        assert other.get('/api/session').status_code==401
    assert client.post('/api/action',json={'action':'send','version':0,'request_id':str(uuid4())}).status_code==403


def test_request_validation_and_no_private_state(client):
    assert send(client,' ').status_code==422
    r=client.post('/api/turn',json={'text':'x'*13000,'version':0,'request_id':str(uuid4())})
    assert r.status_code==413
    r=client.post('/api/turn',json={'text':'Hello','version':0,'request_id':str(uuid4()),'grant':{'approved':True}})
    assert r.status_code==422
    s=send(client,'My name is Margaret Chen; policy POL-9921').json()
    assert not s['verified'] and s['case_id'] is None
    assert 'Margaret Chen' not in str(s)
    assert 'identity' not in s and 'grant' not in s


def test_model_failure_safe_retry_and_resume(tmp_path):
    class Failure(ScriptedInterpreter):
        async def interpret(self,*args): raise ModelFailure('not logged')
    app=create_app(tmp_path,Failure(),clock=lambda:NOW)
    with TestClient(app) as c:
        s=c.post('/api/session').json(); c.headers['x-csrf-token']=s['csrf']
        assert send(c,'My name is Margaret Chen').status_code==503
        assert c.get('/api/session').json()['version']==0
        app.state.interpreter  # Interpreter is closure-bound; restart uses persisted state.
        cookies=c.cookies
    with TestClient(create_app(tmp_path,ScriptedInterpreter(),clock=lambda:NOW)) as c:
        c.cookies.update(cookies)
        assert c.get('/api/session').json()['version']==0
        c.headers['x-csrf-token']=s['csrf']
        assert send(c,'My name is Margaret Chen').status_code==200
    assert b'Margaret Chen' not in (tmp_path/'sessions.sqlite3').read_bytes()


def test_durable_leases_and_request_fingerprints(tmp_path):
    store=Store(tmp_path)
    cookie,csrf,s=store.create(NOW)
    state,lease=store.acquire(cookie,'a',0,'fingerprint',NOW)
    with pytest.raises(Conflict):store.acquire(cookie,'b',0,'second',NOW)
    recovered,newlease=store.acquire(cookie,'b',0,'second',NOW+46)
    with pytest.raises(Conflict):store.commit(cookie,lease,'a','fingerprint',state,NOW+47)
    store.commit(cookie,newlease,'b','second',recovered,NOW+47)
    assert store.acquire(cookie,'b',0,'second',NOW+48)[1] is None
    with pytest.raises(Conflict):store.acquire(cookie,'b',1,'different',NOW+48)
    with pytest.raises(Conflict):store.acquire(cookie,'c',0,'c',NOW+48)
    store.reserve_tokens(12000,12000,NOW)
    with pytest.raises(Limited):Store(tmp_path).reserve_tokens(1,12000,NOW)
    cookie2,_,_=store.create(NOW)
    state2,lease2=store.acquire(cookie2,'cap',0,'cap',NOW)
    state2.version=119
    store.commit(cookie2,lease2,'cap','cap',state2,NOW+1)
    with pytest.raises(Limited):store.acquire(cookie2,'over-cap',120,'over-cap',NOW+2)


@pytest.mark.parametrize('scenario_id',[s['id'] for s in scenarios()])
def test_shared_evaluation_scenarios(scenario_id):
    result=run_scenario(scenario_id)
    assert result['passed'],[x for x in result['checks'] if not x['passed']]


def test_lab_is_scripted_and_does_not_modify_chat(client):
    before=client.get('/api/session').json()
    catalog=client.get('/api/evaluations').json()
    result=client.post('/api/evaluations/'+catalog[0]['id']).json()
    assert result['passed'] and 'Scripted' in result['mode']
    after=client.get('/api/session').json()
    assert before['messages']==after['messages'] and before['version']==after['version']
